#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every row in the phone menu starts its text in the same column.

    python scripts/check_sheet_align.py
    python scripts/check_sheet_align.py --live

Why this exists
---------------
Reported from a phone, about the open menu: the subscribe row "seems to be
off... not in sync with what we currently have at the top". It was, by 38px.

Measured in the open sheet at 390px:

    Portfolio     stone x=21   label x=41
    Blog (here)   stone x=21   label x=44
    Intelligence  stone x=21   label x=41
    Live status   stone x=21   label x=41
    Subscribe     no stone     label x=3

Three separate faults, one of which nobody had reported:

  - .ck-sub-open declared `padding: 0`, directly under a comment saying the
    row "needs the same look the links beside it already have". It inherited
    the colour and none of the box, so it was a block button at zero padding
    with its text against the edge of the screen.
  - the current row's stone grows from 9px to 12px to say "you are here",
    which also pushed its label 3px right -- so the one line meant to read as
    here was the one line out of column.
  - on the portfolio, the page's own section links (About, Writing, Skills,
    Contact, Tools) carry no stone and so sat at x=21, a second list that
    looked like it had lost its indent.

The check is one property and it is the one a reader sees: take every row in
the open sheet and require the x of its label to be identical. That needs no
list of which rows should have a stone and no per-page expectations, and it
catches a new row added later that forgets the column.

Opening the sheet is part of it. Everything here is inside a max-width:1080px
block behind a button, so nothing that only loads a page can see any of it.
"""
import argparse
import http.server
import os
import random
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = [("portfolio", "/"), ("blog", "/blog/"), ("hub", "/intelligence/"),
         ("whats-new", "/intelligence/whats-new/"),
         ("status", "/intelligence/status/")]

ROWS = r"""() => {
  const sheet = document.querySelector('.ck-sheet');
  if (!sheet) return null;
  return [].slice.call(sheet.querySelectorAll('a, button.ck-sub-open'))
    .filter(function (e) { const r = e.getBoundingClientRect();
                           return r.width > 0 && r.height > 0; })
    .map(function (e) {
      const lab = e.querySelector('.ck-label');
      const dot = e.querySelector('.ck-dot');
      const t = (lab || e).getBoundingClientRect();
      return {
        text: ((lab || e).textContent || '').trim().slice(0, 18),
        labelX: Math.round(t.x),
        dotX: dot ? Math.round(dot.getBoundingClientRect().x) : null
      };
    });
}"""


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(9961, 9999):
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
            for name, path in PAGES:
                ctx = b.new_context(**pw.devices["iPhone 13"])
                pg = ctx.new_page()
                url = base + path
                if args.live:
                    url += "?n=%d" % random.randint(1, 999999)
                pg.goto(url, wait_until="load", timeout=90000)
                pg.wait_for_timeout(2200)
                try:
                    pg.click("#ck-btn", timeout=8000)
                    pg.wait_for_timeout(700)
                except Exception as exc:                        # noqa: BLE001
                    problems.append("%s: could not open the menu (%s)"
                                    % (name, str(exc)[:45]))
                    ctx.close()
                    continue
                rows = pg.evaluate(ROWS)
                ctx.close()

                if not rows:
                    problems.append("%s: the menu opened with no rows in it"
                                    % name)
                    continue
                cols = sorted({r["labelX"] for r in rows})
                dots = sorted({r["dotX"] for r in rows if r["dotX"] is not None})
                if len(cols) > 1:
                    worst = max(cols) - min(cols)
                    problems.append(
                        "%s: %d text columns in one menu, %dpx apart -- %s"
                        % (name, len(cols), worst,
                           "; ".join("%s at %d" % (r["text"], r["labelX"])
                                     for r in rows
                                     if r["labelX"] != cols[0])[:110]))
                    print("     FAIL %-11s labels at %s" % (name, cols))
                elif len(dots) > 1:
                    problems.append("%s: stones at %s, which should share an "
                                    "edge too" % (name, dots))
                    print("     FAIL %-11s stones at %s" % (name, dots))
                else:
                    print("     ok   %-11s %d row(s), all text at x=%d"
                          % (name, len(rows), cols[0]))
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PAGE(S) WHERE THE MENU DOES NOT LINE UP\n" % len(problems))
        for x in problems[:10]:
            print("  - %s" % x)
        print("\n  A row that starts 38px left of the ones above it reads as")
        print("  loose text, not as another line of the same list.")
        return 1
    print("  Every row in the menu shares one text column, on %d pages."
          % len(PAGES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
