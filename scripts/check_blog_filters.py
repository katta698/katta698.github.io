#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check the blog index stays light AND still searches the whole archive.

    python scripts/check_blog_filters.py
    python scripts/check_blog_filters.py --url https://jayanthkatta.com/blog/

Why this exists
---------------
The blog index ships one page of cards and fetches the rest from cards.json.
That fetch used to run at idle on every visit -- requestIdleCallback with a
2500ms timeout, which on a phone fires whether the browser is idle or not --
building 199 extra cards into the page for a reader looking at 24. Traced on
an emulated phone, this page spent 3.35s painting and 3.34s in layout.

It is now fetched only when something needs it. That is strictly better for
the common case and it introduces a failure that is invisible from the page:
if any entry point forgets to wait for the fetch, filtering silently searches
the newest 24 posts and reports that as the archive. Nothing looks broken --
a search just returns fewer results than it should, and only someone who knew
the post existed would notice.

So this asserts both halves at once, which is the only way either is safe:
the page must be light on arrival, and every way in must still see all of it.
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8961


def _serve(handler, port):
    """A local server on `port`, or the next free one after it.

    Every one of these checks hardcodes a port, and a run that is interrupted
    leaves the socket held -- so the next run dies with WinError 10048 and
    reports nothing at all. That is worse than a failure: a check that cannot
    start looks exactly like a check that was not run, and it cost several
    rounds today at exactly the moment the answer mattered.
    """
    import socketserver as _ss
    _ss.TCPServer.allow_reuse_address = True
    for p in range(port, port + 40):
        try:
            return _ss.TCPServer(("127.0.0.1", p), handler), p
        except OSError:
            continue
    raise SystemExit("no free port in %d-%d" % (port, port + 40))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=None)
    args = ap.parse_args()

    os.chdir(ROOT)
    with open(os.path.join(ROOT, "blog", "cards.json"), encoding="utf-8") as fh:
        cards = json.load(fh)
    total = len(cards)
    oldest = sorted(cards, key=lambda c: c.get("date", ""))[0]

    srv = None
    base = args.url
    if not base:
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        srv, PORT_USED = _serve(Quiet, PORT)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d/blog/" % PORT_USED
    base = base.rstrip("/") + "/"

    from playwright.sync_api import sync_playwright

    problems = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900})

        # 1. Light on arrival. Waited out well past the old idle timeout.
        pg.goto(base, wait_until="load", timeout=90000)
        pg.wait_for_timeout(4000)
        n = pg.eval_on_selector_all(".post-card", "els => els.length")
        nodes = pg.evaluate("() => document.getElementsByTagName('*').length")
        print("  on arrival: %d cards, %d DOM nodes (archive holds %d posts)"
              % (n, nodes, total))
        if n >= total:
            problems.append(
                "the whole archive is built on arrival (%d cards) -- the page "
                "is paying for %d posts nobody asked for" % (n, total - n + n))

        # 2. A filter still covers everything.
        #
        # The index has no search box of its own -- the magnifier in the bar is
        # the site-wide search -- so the pills are the way in.
        pill = pg.query_selector('.filter-pill[data-tag="aws architecture series"]')
        if not pill:
            problems.append("no filter pill to click; this check cannot run")
        else:
            pill.click()
            pg.wait_for_timeout(3000)
            built = pg.eval_on_selector_all(".post-card", "els => els.length")
            shown = pg.evaluate(
                "() => [...document.querySelectorAll('.post-card')]"
                ".filter(e => getComputedStyle(e).display !== 'none').length")
            print("  after one filter click: %d cards built, %d shown"
                  % (built, shown))
            if built < total:
                problems.append(
                    "a filter searched %d of %d posts -- the rest were never "
                    "fetched, so the result is quietly short" % (built, total))

        # 3. Sorting oldest-first has to reach the actual oldest post.
        pg.click('.filter-pill[data-tag="all"]')
        pg.wait_for_timeout(800)
        sort = pg.query_selector(".sort-btn")
        if sort:
            sort.click()
            pg.wait_for_timeout(3000)
            first = pg.evaluate(
                """() => {
                     const c = [...document.querySelectorAll('.post-card')]
                       .find(e => getComputedStyle(e).display !== 'none');
                     return c ? c.dataset.date : null;
                   }""")
            print("  sorted oldest-first, first card is dated %s "
                  "(archive starts %s)" % (first, oldest["date"]))
            if not first or first > oldest["date"]:
                problems.append(
                    '"Oldest" shows %s when the archive starts at %s -- it '
                    "sorted the page, not the archive" % (first, oldest["date"]))

        # 4. A deep link filters with no click to hang the fetch off.
        pg2 = b.new_page(viewport={"width": 1280, "height": 900})
        pg2.goto(base + "?tag=aws+architecture+series",
                 wait_until="load", timeout=90000)
        pg2.wait_for_timeout(4000)
        built2 = pg2.eval_on_selector_all(".post-card", "els => els.length")
        print("  ?tag= deep link: %d cards built" % built2)
        if built2 < total:
            problems.append(
                "a ?tag= link filtered %d of %d posts -- a shared link returns "
                "matches from the newest page only" % (built2, total))
        pg2.close()

        b.close()
    if srv:
        srv.shutdown()

    if problems:
        print("\n  %d PROBLEM(S)\n" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("\n  the page arrives light and every way in still sees all %d posts."
          % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
