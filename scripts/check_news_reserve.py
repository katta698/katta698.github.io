#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What's New must not change height under the reader.

    python scripts/check_news_reserve.py
    python scripts/check_news_reserve.py --live

Why this exists
---------------
Reported from an iPhone: opening or refreshing What's New scrolls quickly and
then settles. The page ships almost empty and the script renders 60
announcements into it, so the document arrived 1,549px tall and became 7,990px
about half a second later -- a fifth of its height, for long enough for the
browser to act on it. The address bar un-collapses and re-collapses; a restored
scroll position is clamped to a short document and then re-applied to a long
one. Either reads as the page scrolling by itself.

Neither headless Chromium nor headless WebKit reproduced the movement -- both
restore scroll differently from Safari on a phone -- so the fix targets the
measurable cause instead: the page now reserves the room the list will need.

That reservation is two measured constants (107px a row where titles wrap, 69px
where they do not, 20px a day heading) multiplied by counts taken at build
time. Constants drift: a design change to the row, or a longer average title,
and the reservation is wrong again -- too small and the jump comes back, too
large and the page opens on a tall blank and shrinks instead. Neither would
show up anywhere else, because the page renders correctly either way.

So this measures what actually happens: sample the document height from first
paint until it settles, and fail if any single step is large enough for a
reader to notice. The threshold is in pixels rather than a ratio because what
matters is how far the content under a thumb moves.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = "/intelligence/whats-new/"
WIDTHS = [390, 834, 1280]
# Half a line of body text. Below this nothing perceptibly moves; above it, the
# reader's place on the page does.
BUDGET = 400


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(8601, 8651):
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
            for engine, label in (("chromium", "Chrome / Edge"),
                                  ("webkit", "Safari, iPad, iPhone")):
                b = getattr(pw, engine).launch()
                for w in WIDTHS:
                    pg = b.new_page(viewport={"width": w, "height": 844})
                    # commit, not load: the point is to watch from the first
                    # frame, and waiting for load would miss the jump entirely.
                    pg.goto(base + PATH, wait_until="commit", timeout=60000)
                    heights = []
                    for _ in range(14):
                        pg.wait_for_timeout(220)
                        heights.append(pg.evaluate(
                            "() => document.body.scrollHeight"))
                    reserved = pg.evaluate(
                        "() => {const l = document.getElementById('list');"
                        " return !!l && l.classList.contains('list-reserved');}")
                    pg.close()

                    steps = [abs(b2 - a) for a, b2 in zip(heights, heights[1:])]
                    worst = max(steps) if steps else 0
                    ok = worst <= BUDGET
                    print("    %4dpx  %6d -> %6d  biggest step %5dpx  %s"
                          % (w, heights[0], heights[-1], worst,
                             "ok" if ok else "FAIL"))
                    if not ok:
                        problems.append(
                            "%s at %dpx: the page height moved %dpx in one step "
                            "(budget %dpx) — %d to %d"
                            % (label, w, worst, BUDGET,
                               heights[0], heights[-1]))
                    # A reservation that is never released leaves a filtered
                    # view sitting on a tall blank.
                    if reserved:
                        problems.append(
                            "%s at %dpx: the reservation was still in place "
                            "after rendering" % (label, w))
                print("  %s" % label)
                b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for p in problems[:12]:
            print("  - %s" % p)
        print("\n  A page that changes height after it is drawn takes the")
        print("  reader's place on it away.")
        return 1
    print("  What's New holds its height from first paint, within %dpx, on"
          % BUDGET)
    print("  %d widths in both engines." % len(WIDTHS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
