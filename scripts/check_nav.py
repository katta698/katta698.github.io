#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Drive the navigation on every page at every width and check it holds.

    python scripts/check_nav.py

Why this exists
---------------
The nav has now broken four separate ways in one evening, each time from a
change that was correct for the page it was written against and wrong for one
of the others:

  the five links wrapped onto two and three rows, differently at every width
  the palette panel hung 160px off the left edge once the bar wrapped
  two orphan braces killed the brand mark rule on two pages, so the favicon
    rendered as a stretched square while the other three showed a circle
  the collapse matched links by href, and the brand mark is a link to "/",
    so the favicon disappeared from every page below 1080px

Every one of those was found by a reader looking at a phone, which is the
worst possible detector: it only fires on the pages someone happens to open,
and only after the change is live.

So this asserts the four things the bar has to do, on five page types at six
widths, and fails the build when one of them stops being true.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8941

PAGES = [
    ("portfolio", "/"),
    ("blog", "/blog/"),
    ("hub", "/intelligence/"),
    ("status", "/intelligence/status/"),
    ("whats-new", "/intelligence/whats-new/"),
]
WIDTHS = [320, 390, 768, 920, 1100, 1440]

DESTINATIONS = ["/", "/blog/", "/intelligence/",
                "/intelligence/whats-new/", "/intelligence/status/"]

PROBE = """() => {
  const nav = document.querySelector('nav') || document.querySelector('.nav');
  if (!nav) return { fatal: 'no nav' };

  // Nothing may stick out of the window, and the page must not scroll sideways.
  let edge = 0;
  nav.querySelectorAll('*').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width > 0 && r.right > edge) edge = r.right;
  });
  window.scrollTo(300, 0);
  const sideways = window.scrollX;
  window.scrollTo(0, 0);

  const mark = document.querySelector('.brand-mark');
  const mr = mark ? mark.getBoundingClientRect() : null;

  // Every destination reachable, whether in the bar or behind the mark.
  const sheet = document.querySelector('.ck-sheet');
  const inBar = [...nav.querySelectorAll('a[href]')]
    .filter(a => a.getBoundingClientRect().width > 0)
    .map(a => a.getAttribute('href'));
  const inSheet = sheet ? [...sheet.querySelectorAll('a[href]')]
    .map(a => a.getAttribute('href')) : [];

  // And the current page said out loud, one way or the other.
  const here = document.querySelector('.ck-here');
  const active = document.querySelector('.nav-links a.active, .ck-sheet a.is-here');

  return {
    edge: Math.round(edge), vw: window.innerWidth, sideways,
    markVisible: !!(mr && mr.width > 0 && mr.height > 0),
    markRadius: mark ? getComputedStyle(mark).borderRadius : null,
    reach: [...new Set(inBar.concat(inSheet))],
    saysWhere: !!((here && here.textContent.trim()) || active)
  };
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="webkit",
                    choices=["webkit", "chromium", "firefox"])
    args = ap.parse_args()

    os.chdir(ROOT)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    srv = socketserver.TCPServer(("127.0.0.1", PORT), Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    from playwright.sync_api import sync_playwright

    problems = []
    with sync_playwright() as pw:
        browser = getattr(pw, args.engine).launch()
        for name, path in PAGES:
            notes = []
            for w in WIDTHS:
                pg = browser.new_page(viewport={"width": w, "height": 820})
                pg.goto("http://127.0.0.1:%d%s" % (PORT, path),
                        wait_until="networkidle", timeout=60000)
                pg.wait_for_timeout(900)
                r = pg.evaluate(PROBE)
                tag = "%s@%d" % (name, w)

                if r.get("fatal"):
                    problems.append("%s: %s" % (tag, r["fatal"]))
                    pg.close()
                    continue
                if r["edge"] > r["vw"] + 1:
                    problems.append("%s: the bar is %dpx wide in a %dpx window"
                                    % (tag, r["edge"], r["vw"]))
                if r["sideways"]:
                    problems.append("%s: the page scrolls sideways" % tag)
                if not r["markVisible"]:
                    problems.append("%s: the brand mark is not visible" % tag)
                elif r["markRadius"] != "50%":
                    problems.append("%s: the brand mark is not round (%s)"
                                    % (tag, r["markRadius"]))
                missing = [d for d in DESTINATIONS if d not in r["reach"]]
                if missing:
                    problems.append("%s: cannot reach %s"
                                    % (tag, ", ".join(missing)))
                if not r["saysWhere"]:
                    problems.append("%s: nothing says which page this is" % tag)
                notes.append("%d:%d" % (w, r["edge"]))
                pg.close()
            print("  %-10s widths ok, bar width by viewport: %s"
                  % (name, " ".join(notes)))
        browser.close()
    srv.shutdown()

    if problems:
        print("\n  %d NAVIGATION PROBLEM(S)\n" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("\n  the bar fits, the mark shows, every page is reachable, and each")
    print("  page says which one it is -- on %d pages at %d widths."
          % (len(PAGES), len(WIDTHS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
