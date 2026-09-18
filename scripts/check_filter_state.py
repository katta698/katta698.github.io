#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every filtered page comes back the way you left it.

    python scripts/check_filter_state.py
    python scripts/check_filter_state.py --live

Why this exists
---------------
Reported as: "when I filter AWS and last seven days and a specific service,
click the link, it opens a new tab -- and when I go back it's resetting to
all. Can it be in the same state as before we opened the link?" Then, once it
was fixed on that page: "just ensure you maintain the same behaviour across
anything in the page."

That second sentence is the one this file is for. Three pages on this site let
a reader narrow a long list, and every one of them sends that reader OUT to a
vendor's page or a post -- which is the whole point of them. So on all three,
"I come back" is part of normal use, not an edge case.

They did not behave the same way. Cloud events kept its filters in the URL.
What's New kept nothing. The blog kept nothing, while already reading ?tag=
and ?q= on the way in -- so a link could arrive filtered but a reader could
never leave and return to their own view. Nothing about any of this looks
broken on screen: the page simply comes back as if you had just arrived, and
the reader does the work again.

One check for all three, rather than three checks, because the requirement is
that they AGREE. Three separate files is how one of them quietly stops
matching the other two.

What it asserts is the reader's sequence, not the mechanism: set filters,
RELOAD (the worst case -- the back/forward cache would restore the variables
and hide the bug), and require the same controls lit and the same rows. A
check that only read the URL would pass a page that writes state and ignores
it on the way back in.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


# Each page: where it lives, what a reader clicks, how to read its state back,
# and what its unfiltered count looks like.
#
# The "state" reader returns only what a READER can see -- which controls are
# lit, what is in the search box, how many rows are showing. Deliberately not
# the URL: a page that writes a perfect URL and ignores it on reload has the
# reported bug, and reading the URL back would call that a pass.
PAGES = [
    {
        "name": "What's new",
        "path": "/intelligence/whats-new/",
        "settle": 2600,
        "steps": [
            ('#clouds .pill[data-cloud="aws"]', "cloud"),
            ('#clouds .pill[data-days="7"]', "date range"),
            ('#svcs .pill[data-svc]:not([data-svc=""])', "service"),
        ],
        "search": "#q",
        "row": "#list .item .title",
        "state": """() => {
          const lit = s => [...document.querySelectorAll(s)]
              .filter(b => b.classList.contains('on'))
              .map(b => b.textContent.replace(/^\\u00d7\\s*/, '').trim());
          return {
            controls: [ ...lit('#clouds .pill[data-cloud]'),
                        ...lit('#clouds .pill[data-days]'),
                        ...[...document.querySelectorAll('#svcs .pill.on')]
                             .map(b => b.textContent
                                  .replace(/^\\u00d7\\s*/, '').trim()) ],
            q: document.getElementById('q').value,
            rows: document.querySelectorAll('#list .item').length
          };
        }""",
        "junk": "?cloud=oracle&days=4000&svc=Nonesuch",
    },
    {
        "name": "Cloud events",
        "path": "/intelligence/events/",
        "settle": 2200,
        "steps": [
            ('.ev-pill[data-group="cloud"][data-value="azure"]', "cloud"),
            ('.ev-pill[data-group="type"][data-value="tour"]', "type"),
        ],
        "search": None,
        "row": None,
        "state": """() => ({
          controls: [...document.querySelectorAll(
              '.ev-pill[aria-pressed="true"]')]
              .filter(b => b.dataset.value !== 'all')
              .map(b => b.textContent.trim()),
          q: '',
          rows: [...document.querySelectorAll('.ev-row')]
                  .filter(r => r.style.display !== 'none').length
        })""",
        "junk": "?cloud=oracle&type=hackathon&region=mars",
    },
    {
        "name": "Blog",
        "path": "/blog/",
        "settle": 4000,
        "steps": [
            ('.year-filters .filter-pill[data-year]:not([data-year="all"])',
             "year"),
            (".sort-btn", "sort order"),
        ],
        # The blog index has no search box of its own -- the magnifier in
        # the bar is the site-wide search -- so the pills and the sort button
        # are the controls a reader actually sets here.
        "search": None,
        "row": None,
        "state": """() => ({
          controls: [
            ...[...document.querySelectorAll(
                 '.year-filters .filter-pill.active')]
                 .map(b => 'year ' + b.dataset.year)
                 .filter(t => t !== 'year all'),
            ...[...document.querySelectorAll(
                 '.month-filters .filter-pill.active')]
                 .map(b => 'month ' + b.dataset.month)
                 .filter(t => t !== 'month all'),
            (document.querySelector('.sort-btn') || {}).textContent
              ? document.querySelector('.sort-btn').textContent.trim()
              : ''
          ].filter(Boolean),
          q: (document.getElementById('blog-search') || {}).value || '',
          rows: [...document.querySelectorAll('.post-card')]
                  .filter(c => getComputedStyle(c).display !== 'none').length
        })""",
        "junk": "?year=1998&month=99&sort=sideways",
    },
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--only", default=None,
                    help="run one page by name, e.g. --only blog")
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
            for spec in PAGES:
                if args.only and args.only.lower() not in spec["name"].lower():
                    continue
                print("  %s  (%s)" % (spec["name"], spec["path"]))
                ctx = b.new_context(viewport={"width": 1280, "height": 900})
                pg = ctx.new_page()
                pg.goto(base + spec["path"], wait_until="load", timeout=90000)
                pg.wait_for_timeout(spec["settle"])

                unfiltered = pg.evaluate(spec["state"])["rows"]

                used = []
                for sel, label in spec["steps"]:
                    el = pg.query_selector(sel)
                    if not el:
                        problems.append(
                            "%s: no %s control to click (%s) -- this check "
                            "cannot exercise it" % (spec["name"], label, sel))
                        continue
                    el.click()
                    pg.wait_for_timeout(1100)
                    used.append(label)

                # The search term comes off a row that is ON SCREEN. Typing a
                # guess produced a 0-row view that then "survived" the reload
                # perfectly, because 0 == 0. A restore check that restores
                # nothing visible is not a check. (CHECKLIST rule 6.)
                if (spec["search"] and spec["row"]
                        and pg.query_selector(spec["search"])):
                    word = pg.evaluate(
                        """(sel) => {
                             const e = document.querySelector(sel);
                             if (!e) return null;
                             return (e.textContent.match(/[A-Za-z]{5,}/g)
                                     || [])[0] || null;
                           }""", spec["row"])
                    if word:
                        pg.fill(spec["search"], word)
                        pg.wait_for_timeout(1400)
                        used.append("search")

                before = pg.evaluate(spec["state"])
                url = pg.evaluate("() => location.search")
                print("     filtered   %s | q=%r | %d row(s)"
                      % (before["controls"], before["q"], before["rows"]))
                print("     url        %s" % (url or "(none)"))

                if not url:
                    problems.append(
                        "%s: %s changed and the URL stayed empty -- there is "
                        "nothing for a reload to restore, and nothing to send "
                        "to anybody" % (spec["name"], " and ".join(used)))

                if before["rows"] == 0:
                    problems.append(
                        "%s: the filtered view this check built has 0 rows, "
                        "so a reload restoring 0 rows would prove nothing"
                        % spec["name"])
                elif before["rows"] == unfiltered:
                    problems.append(
                        "%s: %d rows filtered and %d unfiltered -- the "
                        "controls are lit and nothing was filtered"
                        % (spec["name"], before["rows"], unfiltered))

                # A reload, not the back button: bfcache would restore the
                # variables and hide exactly the reported failure, which is a
                # tab the browser threw away while the reader was elsewhere.
                pg.reload(wait_until="load", timeout=90000)
                pg.wait_for_timeout(spec["settle"] + 1200)
                after = pg.evaluate(spec["state"])
                print("     reloaded   %s | q=%r | %d row(s)"
                      % (after["controls"], after["q"], after["rows"]))

                if before["controls"] != after["controls"]:
                    problems.append(
                        "%s: the controls read %s before leaving and %s on "
                        "return -- a reader has to set them again every time "
                        "they read something"
                        % (spec["name"], before["controls"], after["controls"]))
                if before["q"] != after["q"]:
                    problems.append(
                        "%s: the search box held %r and came back %r"
                        % (spec["name"], before["q"], after["q"]))
                if before["rows"] != after["rows"]:
                    problems.append(
                        "%s: %d rows before leaving, %d on return -- the "
                        "controls may look restored while the list is not"
                        % (spec["name"], before["rows"], after["rows"]))
                ctx.close()

                # A stale or hand-edited link must not be able to empty the
                # page. ?year=1998 should show the archive, not nothing under
                # a lit pill.
                ctx = b.new_context(viewport={"width": 1280, "height": 900})
                pg = ctx.new_page()
                pg.goto(base + spec["path"] + spec["junk"],
                        wait_until="load", timeout=90000)
                pg.wait_for_timeout(spec["settle"] + 800)
                junk = pg.evaluate(spec["state"])
                print("     junk url   %s | %d row(s)"
                      % (junk["controls"], junk["rows"]))
                if junk["rows"] == 0:
                    problems.append(
                        "%s: %s rendered an empty page -- a stale or "
                        "hand-edited link should fall back to the default "
                        "view, not to nothing"
                        % (spec["name"], spec["junk"]))
                ctx.close()
                print()
            b.close()
    finally:
        if srv:
            srv.shutdown()

    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for p in problems:
            print("  - %s" % p)
        print()
        print("  Filters that reset on return look like a page that was never")
        print("  filtered. Nothing errors, and the reader does it all again.")
        return 1
    print("  All three filtered pages come back the way they were left.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
