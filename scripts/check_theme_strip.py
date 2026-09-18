#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The strip above the page is the same colour as the page.

    python scripts/check_theme_strip.py
    python scripts/check_theme_strip.py --live

Why this exists
---------------
Reported as: "resume page looks different -- when you shift between dark and
light mode somehow things are off", with a screenshot of a dark page wearing a
cream band across the top.

That band is <html>. Every page sets its background in an inline <head>
script, read from localStorage, so the first frame is already the right colour
rather than a white flash -- and nothing ever updated it again. All four
toggleTheme() implementations change `body.light` and stop. Measured after one
toggle, identically on the portfolio, the resume, the blog and the three
Intelligence pages:

    html  rgb(31, 29, 27)      still dark, from load
    body  rgb(250, 242, 242)   light, as asked

A reload cleared it, which is why it lasted: it only shows to a reader who
toggles and then overscrolls, and on a phone that top rubber-band area is
exactly where it shows. Worse, even when the two AGREED they were never the
same colour -- the head scripts use #F7F4EF/#1F1D1B, the pages paint
#FAF2F2/#211C1C -- so a faint band sat at the top of every page, in both
themes, from the beginning.

This asserts what a reader sees rather than how it is done: on load, after a
toggle, and after toggling back, <html> and <body> must compute to the same
background.

The "after a toggle" reading is the one that matters and the one that is
easy to get wrong. The first fix synced on the class change and still failed,
because the portfolio ANIMATES background-color: read at that instant,
getComputedStyle returns the colour it is transitioning from, so html trailed
body by exactly one toggle -- which looks the same as no fix at all. Hence the
waits below, and hence a check that toggles twice.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = ["/", "/resume.html", "/now.html", "/blog/", "/intelligence/",
         "/intelligence/whats-new/", "/intelligence/status/",
         "/intelligence/events/"]

READ = """() => ({
  h: getComputedStyle(document.documentElement).backgroundColor,
  b: getComputedStyle(document.body).backgroundColor
})"""

# Call the page's own toggle rather than hunting for a button. At phone width
# the control lives inside a collapsed menu on some pages, and a check that
# cannot find it would report "no toggle" and pass.
TOGGLE = """() => {
  if (typeof toggleTheme === 'function') { toggleTheme(); return 'fn'; }
  const b = document.querySelector('#theme-btn,.theme-toggle,.nav-mobile-theme');
  if (b) { b.click(); return 'click'; }
  return 'none';
}"""


class _Threaded(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    for port in range(9501, 9551):
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
            for path in PAGES:
                ctx = br.new_context(**pw.devices["iPhone 13"])
                pg = ctx.new_page()
                pg.goto(base + path, wait_until="load", timeout=90000)
                pg.wait_for_timeout(2000)

                stages = [("on load", pg.evaluate(READ))]
                how = pg.evaluate(TOGGLE)
                if how == "none":
                    problems.append(
                        "%s has no theme toggle this check can reach, so it "
                        "cannot assert anything about it" % path)
                    ctx.close()
                    continue
                # Long enough for a background-color transition to finish.
                pg.wait_for_timeout(1400)
                stages.append(("after toggling", pg.evaluate(READ)))
                pg.evaluate(TOGGLE)
                pg.wait_for_timeout(1400)
                stages.append(("toggled back", pg.evaluate(READ)))

                bad = [(w, s) for w, s in stages if s["h"] != s["b"]]
                print("  %-28s %s" % (path, "ok" if not bad else "MISMATCH"))
                for when, s in bad:
                    print("       %-15s html %s vs page %s"
                          % (when, s["h"], s["b"]))
                    problems.append(
                        "%s %s: the strip above the page is %s while the page "
                        "is %s -- a reader who overscrolls sees a band of the "
                        "other theme" % (path, when, s["h"], s["b"]))
                ctx.close()
            br.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for p in problems[:12]:
            print("  - %s" % p)
        print()
        print("  Nothing errors and a reload hides it. It is only visible to")
        print("  someone who switches theme and then pulls past the top.")
        return 1
    print("  All %d pages: html and the page agree on load, after a toggle, "
          "and back." % len(PAGES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
