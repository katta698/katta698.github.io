#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A page must not rebuild its own header in front of the reader.

    python scripts/check_page_settle.py
    python scripts/check_page_settle.py --live

Why this exists
---------------
Reported as: every other page is "static and seamless", but the blog "gets
refreshed" on every visit. It was not a reload -- the HTML came from the
service worker in 5ms and the blog painted FASTEST of the five pages. What
moved was the page's own furniture, inserted by JavaScript a few hundred
milliseconds after paint and shoving the whole post list down:

    .filter-stack   the year and month rows, 102-183px depending on width
    .sort-btn       the "Newest" toggle, 27px

Measured at 1440px before the fix: at 498ms there was no .filter-stack at all;
by 639ms it was 183px and the first card had moved from y=734 to y=863. At
390px the first card moved 666px.

All of it was avoidable. The data was already server-side -- the years come
from data-years on the grid -- and only the DOM building was not. Those rows
are rendered by sync_blog.py now and blog.js reuses them when it finds them,
falling back to building its own for pages built before this.

Reserving space instead was the obvious alternative and the wrong tool: the
stack is 102px at 640, 112px at 1024, 183px at 1440 and 147px at 1920. It does
not ladder, because the topic row wraps differently at each, and it would move
again the day a topic is added. Markup that is simply present is correct at
every width for free.

The budget is deliberately generous. This is not a layout-shift score; it is
"did the page visibly rebuild itself". A reader tolerates a banner settling
in; they do not tolerate the article list jumping half a screen.
"""
import argparse
import json
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["/", "/blog/", "/intelligence/", "/intelligence/whats-new/",
         "/intelligence/status/"]
WIDTHS = [390, 1024, 1440]
# What the budget actually contains today, measured rather than guessed:
#
#   0px   portfolio, Intelligence
#   3px   blog
#   18px  Live status
#   31px  What's New, releasing its row-height reservation at 390px
#
# It was 80 while the occasion banner still arrived after paint and cost every
# page ~37px; that banner is a blocking script in the head now and costs
# nothing. 50 leaves room for the one real settle that remains without leaving
# room for a new fault -- the bug this exists for moved the blog 666px.
BUDGET = 50

# An explicit anchor per page, and the shell on top of that.
#
# This has been wrong twice, both times by guessing at the element. It first
# called querySelector on every tick with a GROUP selector, so it could measure
# <main> early and a .post-card later -- two different elements -- and report
# the distance between them as movement. Pinning the element once fixed that
# and it still reported 512px on the portfolio and 545px on the blog at 390px,
# intermittently, while a direct measurement showed 3px.
#
# The reason: there is no <main> on those pages, so the group fell through to
# an <article> somewhere down the document, whose position legitimately moves
# when an image above it loads. That is a real shift, but it is not what this
# check is for, and reporting it as "the page rebuilt itself" cried wolf.
#
# So: name the anchor. HERO_BOTTOM is the shell -- if the header or the hero
# changes height, everything below moves, and that is the seamlessness being
# asked about. CONTENT is the first block a reader actually reads, named per
# page, which is what caught the filter stack being inserted after paint.
ANCHORS = {
    "/": ".about, .section, .panel",
    "/blog/": "#posts-grid, .posts-grid",
    "/intelligence/": ".wrap, .cards, .grid",
    "/intelligence/whats-new/": "#list, .controls",
    "/intelligence/status/": ".sum, .wrap",
}

INIT_TMPL = """window.__settle=[];window.__a=null;window.__h=null;
(function s(){
  if(!window.__a) window.__a=document.querySelector(%s);
  if(!window.__h) window.__h=document.querySelector('header.hero,section.hero,.hero,nav');
  var a=window.__a, h=window.__h;
  window.__settle.push({
    c: (a&&a.isConnected)?Math.round(a.getBoundingClientRect().top+window.scrollY):null,
    s: (h&&h.isConnected)?Math.round(h.getBoundingClientRect().bottom+window.scrollY):null});
  if(window.__settle.length<42)setTimeout(s,80);
})();"""


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(9001, 9051):
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
            for p in PAGES:
                worst = 0
                for w in WIDTHS:
                    ctx = b.new_context(viewport={"width": w, "height": 900})
                    ctx.add_init_script(
                        INIT_TMPL % json.dumps(ANCHORS.get(p, "body")))
                    pg = ctx.new_page()
                    pg.goto(base + p, wait_until="load", timeout=60000)
                    pg.wait_for_timeout(3400)
                    rows = pg.evaluate("() => window.__settle")
                    ys = [r["c"] for r in rows if r["c"] is not None]
                    shell = [r["s"] for r in rows if r["s"] is not None]
                    ctx.close()
                    if not ys:
                        continue
                    moved = max(max(ys) - min(ys),
                                (max(shell) - min(shell)) if shell else 0)
                    worst = max(worst, moved)
                    if moved > BUDGET:
                        problems.append(
                            "%s at %dpx: the content moved %dpx after it was "
                            "painted (budget %dpx) -- something is being "
                            "inserted above it by script. Render it in the "
                            "HTML instead." % (p, w, moved, BUDGET))
                print("    %-26s worst movement after paint %3dpx" % (p, worst))
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for x in problems[:10]:
            print("  - %s" % x)
        print("\n  This is what 'the page refreshed itself' looks like from")
        print("  the outside. Nothing else reports it.")
        return 1
    print("  Every page settles within %dpx of where it first painted." % BUDGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
