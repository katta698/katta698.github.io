#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What's New keeps your filters when you leave the page and come back.

    python scripts/check_news_state.py
    python scripts/check_news_state.py --live

Why this exists
---------------
Reported as: "when I filter AWS and last seven days and a specific service,
click the link, it opens a new tab -- and when I go back it's resetting to
all. Can it be in the same state as before we opened the link?"

It could not, and nothing said so. The five pieces of state -- cloud, days,
service, the search box, and the blogs/bulletins pool -- lived in JavaScript
variables and nowhere else. Every row links out with target="_blank", so
"coming back" often means a tab the browser discarded and reloaded while the
reader was reading the vendor's page. A reload is the one thing in-memory
state cannot survive, and the page came back looking untouched: all clouds,
30 days, no service. Not an error, not a broken control -- just a reader's
work quietly undone, which is the kind of thing that gets lived with rather
than reported.

The filters now live in the URL, so the state survives a reload, a restore
from the back/forward cache, a phone reclaiming the tab, and a pull-to-refresh
in the installed app. It also makes a filtered view sendable.

What this asserts is the reader's sequence, not the mechanism: set three
filters, RELOAD (the worst case -- bfcache would hide the bug), and require
the same pills lit, the same search text, and the same number of rows. A
check that only read the URL would pass on a page that writes the URL and
ignores it on the way back in.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = "/intelligence/whats-new/"


class _Threaded(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    for port in range(9401, 9451):
        try:
            srv = _Threaded(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


STATE = """() => {
  const on = sel => [...document.querySelectorAll(sel)]
      .filter(b => b.classList.contains('on'))
      .map(b => b.textContent.trim());
  return {
    cloud: on('#clouds .pill[data-cloud]'),
    days:  on('#clouds .pill[data-days]'),
    svc:   [...document.querySelectorAll('#svcs .pill.on')]
             .map(b => b.textContent.replace(/^\\u00d7\\s*/, '').trim()),
    q:     document.getElementById('q').value,
    count: document.getElementById('count').textContent.trim(),
    rows:  document.querySelectorAll('#list .item').length,
    url:   location.search
  };
}"""


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
            pg = b.new_page(viewport={"width": 1280, "height": 900})
            pg.goto(base + PAGE, wait_until="load", timeout=90000)
            pg.wait_for_timeout(2500)

            # The reader's sequence: a cloud, a date range, then a service.
            pg.click('#clouds .pill[data-cloud="aws"]', timeout=8000)
            pg.wait_for_timeout(500)
            pg.click('#clouds .pill[data-days="7"]', timeout=8000)
            pg.wait_for_timeout(500)
            svc = pg.query_selector('#svcs .pill[data-svc]:not([data-svc=""])')
            if svc:
                name = svc.text_content().strip()
                svc.click()
                pg.wait_for_timeout(500)
            else:
                name = None
                problems.append("no service pill to click after filtering to "
                                "AWS and 7 days; this check cannot run its "
                                "third filter")
            # The search term is taken from a row that is ON SCREEN, not
            # typed in from outside. An earlier version searched "update" and
            # built a view with 0 rows -- which then "survived" the reload
            # perfectly, because 0 == 0. A restore check that restores nothing
            # visible is not a check. (CHECKLIST rule 6.)
            word = pg.evaluate(
                """() => {
                     const a = document.querySelector('#list .item .title');
                     if (!a) return null;
                     return (a.textContent.match(/[A-Za-z]{5,}/g) || [])[0]
                            || null;
                   }""")
            if word:
                pg.fill("#q", word)
                pg.wait_for_timeout(700)
            before = pg.evaluate(STATE)
            if before["rows"] == 0:
                problems.append(
                    "the filtered view this check built has 0 rows, so a "
                    "reload restoring 0 rows proves nothing. Filters used: "
                    "%s / %s / %s / q=%r"
                    % (before["cloud"], before["days"], before["svc"],
                       before["q"]))
            print("  filtered:  %s | %s | %s | q=%r | %s"
                  % (before["cloud"], before["days"], before["svc"],
                     before["q"], before["count"]))
            print("  url:       %s" % (before["url"] or "(none)"))

            if not before["url"]:
                problems.append(
                    "three filters and a search left the URL untouched -- "
                    "there is nothing for a reload to restore, and nothing "
                    "to send to anybody")

            # A reload, not a back-button. bfcache would restore the variables
            # and hide exactly the failure this is for: the reported case is a
            # tab the browser threw away.
            pg.reload(wait_until="load", timeout=90000)
            pg.wait_for_timeout(2800)
            after = pg.evaluate(STATE)
            print("  reloaded:  %s | %s | %s | q=%r | %s"
                  % (after["cloud"], after["days"], after["svc"],
                     after["q"], after["count"]))

            for key, label in (("cloud", "the cloud"), ("days", "the date range"),
                               ("svc", "the service"), ("q", "the search box")):
                if before[key] != after[key]:
                    problems.append(
                        "%s was %r before leaving and %r on return -- a reader "
                        "has to set it again every time they read something"
                        % (label, before[key], after[key]))
            if before["count"] != after["count"]:
                problems.append(
                    "the result count was %r and came back %r"
                    % (before["count"], after["count"]))

            # A filtered view has to actually be filtered. Restoring the pills
            # while showing everything is the failure the blog year filter had.
            pg2 = b.new_page(viewport={"width": 1280, "height": 900})
            pg2.goto(base + PAGE, wait_until="load", timeout=90000)
            pg2.wait_for_timeout(2500)
            full = pg2.evaluate(
                "() => document.getElementById('count').textContent.trim()")
            pg2.close()
            print("  unfiltered the page reads: %s" % full)
            if full == after["count"]:
                problems.append(
                    "the restored view shows the same %s as the unfiltered "
                    "page -- the pills came back lit and nothing was filtered"
                    % full)

            # A hand-edited URL must not be able to empty the page.
            pg3 = b.new_page(viewport={"width": 1280, "height": 900})
            pg3.goto(base + PAGE + "?cloud=oracle&days=4000&svc=Nonesuch",
                     wait_until="load", timeout=90000)
            pg3.wait_for_timeout(2800)
            junk = pg3.evaluate(STATE)
            pg3.close()
            print("  junk url:  %s | %s | %s" % (junk["cloud"], junk["days"],
                                                 junk["svc"]))
            if junk["rows"] == 0:
                problems.append(
                    "?cloud=oracle&days=4000 rendered an empty page -- a stale "
                    "or hand-edited link should fall back to the default view, "
                    "not to nothing")

            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for p in problems:
            print("  - %s" % p)
        print()
        print("  Filters that reset on return look like a page that was never")
        print("  filtered. Nothing errors, and the reader does the work again.")
        return 1
    print("  Filters survive a full reload: cloud, date range, service and "
          "search all come back.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
