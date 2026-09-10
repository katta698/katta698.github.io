#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure layout shift in a REAL browser window, not a headless one.

    python scripts/check_shift.py
    python scripts/check_shift.py --url https://jayanthkatta.com/

Why this exists
---------------
A reader reported, perhaps a dozen times across an afternoon, that the
portfolio's navigation moved sideways on a hard refresh. Every check in this
directory said it did not. They were all headless, and headless Chromium and
headless Firefox use OVERLAY scrollbars and lay the bar out slightly
differently from a real Windows Chrome -- so the fault was invisible to every
instrument pointed at it.

Each time, the honest reading of "I measure 0px" was "I cannot see it", and
each time it was reported back as "it is fixed". Meanwhile the same page in a
real browser window on the reporter's own laptop showed the bar jumping 44px,
three times, inside the first second.

So this drives a real Chrome, with a real window and real scrollbars, and
prints what moved and by how much. It is slower and it needs a desktop
session, which is why it is not in CI -- but when someone says a page moves
and the headless checks disagree, this is the one that is right.

The rule this encodes: a report from a human on their own machine outranks a
measurement from an environment that renders differently.
"""
import argparse
import http.server
import os
import re
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = [("portfolio", "/"), ("blog", "/blog/"), ("hub", "/intelligence/"),
         ("whats-new", "/intelligence/whats-new/"),
         ("status", "/intelligence/status/")]

WATCH = """window.__ls = [];
try {
  new PerformanceObserver(function (l) {
    l.getEntries().forEach(function (e) {
      if (e.hadRecentInput) return;
      window.__ls.push({
        v: +e.value.toFixed(4), t: Math.round(e.startTime),
        src: (e.sources || []).map(function (s) {
          var n = s.node; if (!n) return '?';
          return (n.tagName || '').toLowerCase() + '.' +
                 ((n.className || '') + '').split(' ')[0] +
                 ' x' + Math.round(s.previousRect.x) + '->' + Math.round(s.currentRect.x) +
                 ' y' + Math.round(s.previousRect.y) + '->' + Math.round(s.currentRect.y);
        })
      });
    });
  }).observe({ type: 'layout-shift', buffered: true });
} catch (e) {}"""


def biggest(entries, axis):
    worst = 0
    for e in entries:
        for s in e["src"]:
            m = re.search(axis + r"(-?\d+)->(-?\d+)", s)
            if m:
                worst = max(worst, abs(int(m.group(1)) - int(m.group(2))))
    return worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=None, help="test a deployed site instead")
    ap.add_argument("--budget", type=float, default=6.0,
                    help="pixels of movement allowed in the bar")
    args = ap.parse_args()

    os.chdir(ROOT)
    srv = None
    base = args.url.rstrip("/") if args.url else None
    if not base:
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def end_headers(self):
                if self.path.endswith(".woff2"):
                    self.send_header("Access-Control-Allow-Origin", "*")
                http.server.SimpleHTTPRequestHandler.end_headers(self)

        socketserver.TCPServer.allow_reuse_address = True
        port = None
        for p in range(8951, 8991):
            try:
                srv = socketserver.TCPServer(("127.0.0.1", p), Quiet)
                port = p
                break
            except OSError:
                continue
        if not srv:
            print("  no free port"); return 1
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % port

    from playwright.sync_api import sync_playwright

    problems = []
    print("  a real Chrome window -- real scrollbars, real text rendering")
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=False, channel="chrome")
        except Exception as exc:                                # noqa: BLE001
            print("  cannot open a real Chrome (%s)" % str(exc)[:60])
            print("  this check needs a desktop session; it is not a CI check.")
            if srv:
                srv.shutdown()
            return 0
        for name, path in PAGES:
            ctx = browser.new_context(viewport=None)   # a real window
            pg = ctx.new_page()
            pg.add_init_script(WATCH)
            pg.goto(base + path, wait_until="load", timeout=120000)
            pg.wait_for_timeout(7000)
            entries = pg.evaluate("() => window.__ls")
            bar = [e for e in entries
                   if any("nav-links" in s or "nav-actions" in s or "nav-logo" in s
                          for s in e["src"])]
            cls = sum(e["v"] for e in entries)
            sideways = biggest(bar, "x")
            print("   %-11s CLS %.4f | bar shifts %d | sideways %dpx"
                  % (name, cls, len(bar), sideways))
            if sideways > args.budget:
                problems.append("%s: the bar moves %dpx sideways after first paint"
                                % (name, sideways))
                for e in bar[:3]:
                    print("        t=%-5d %s" % (e["t"], e["src"][0]))
            ctx.close()
        browser.close()
    if srv:
        srv.shutdown()

    if problems:
        print("\n  %d PAGE(S) WHERE THE BAR MOVES\n" % len(problems))
        for p in problems:
            print("  - %s" % p)
        print("\n  Anything that changes the width of something in the bar after")
        print("  first paint does this: an element injected by JS, a font that")
        print("  swaps, a scrollbar that appears, or space reserved for a control")
        print("  that has not arrived yet.")
        return 1
    print("\n  nothing in the bar moves after first paint, on %d pages." % len(PAGES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
