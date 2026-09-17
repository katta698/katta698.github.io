#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The mark and the wordmark are identical on every page.

    python scripts/check_brand.py
    python scripts/check_brand.py --live

Why this exists
---------------
Reported as: "is Jayanth Katta and the favicon logo beside it similar across
all tabs? On portfolio it's kind of shrinking, on blog it's kind of changing."

Almost all of it was already identical, and that is worth recording because it
is what made the real difference hard to see: same file (brand-mark-96.png),
same 96x96 source drawn at 30x30, same 50% radius, no filter, same Playfair
Display at exactly 96.6px wide, and no font swap on any page -- the width never
moved after paint anywhere.

What differed was one number. The gap between the mark and the name was .65rem
on the portfolio and the blog and .6rem on the three Intelligence pages, so the
wordmark sat 0.8px further out on two tabs than on the other three. There were
five copies of that rule -- blog.css, index.html, intelligence/index.html,
status.css and build_news_page.py -- which is the actual fault: a value
restated five times drifts, and 0.8px is small enough that it drifts unnoticed
for a long time.

The portfolio also set font-size 1.05rem on the logo in a phone media query
against 1rem everywhere else. Invisible, because the wordmark is display:none
at that width, which is exactly why it survived.

This measures the rendered result rather than the rules, so it does not care
how many copies exist or which one wins -- only that all five pages agree.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["/", "/blog/", "/intelligence/", "/intelligence/whats-new/",
         "/intelligence/status/"]
WIDTHS = [1440, 390]
# Sub-pixel layout differs harmlessly between engines; 0.5px is well inside
# "identical" and well below the 0.8px that was actually reported.
TOL = 0.5

PROBE = r"""() => {
  const mark = document.querySelector('.nav-logo img, .brand-mark');
  const name = document.querySelector('.brand-name');
  if (!mark) return null;
  const mr = mark.getBoundingClientRect();
  const ms = getComputedStyle(mark);
  const out = {
    markX: mr.x, markY: mr.y, markW: mr.width, markH: mr.height,
    src: (mark.currentSrc || mark.src || '').split('/').pop(),
    radius: ms.borderRadius,
    nameShown: false, nameX: 0, nameW: 0, nameFS: '', gap: 0
  };
  if (name) {
    const ns = getComputedStyle(name);
    if (ns.display !== 'none' && ns.visibility !== 'hidden') {
      const nr = name.getBoundingClientRect();
      out.nameShown = true;
      out.nameX = nr.x; out.nameW = nr.width; out.nameFS = ns.fontSize;
      out.gap = nr.x - (mr.x + mr.width);
    }
  }
  return out;
}"""


def settle(pg, ms=2400):
    """Wait for the webfonts, not for a guess at how long they take.

    This used to be a flat 2400ms, which is plenty on its own and not
    plenty when six headless browsers are sharing one machine and one
    local server. Under the full preflight run this check reported

        1440px: wordmark width differs on /intelligence/ -- 114.8 against 96.6

    and passed on its own immediately after. 114.8 is the wordmark drawn in
    the fallback serif; 96.6 is Playfair Display. Nothing about the site had
    changed between the two runs -- the font simply had not arrived yet.

    document.fonts.ready is the property that was actually meant all along:
    it resolves when font loading has finished, however long that takes. The
    timeout is a floor, not a promise, so a machine under load waits longer
    and a quiet one does not wait at all.

    Kept deliberately short after that, because a check that is reliable and
    slow gets bypassed just like one that is fast and flaky.
    """
    try:
        pg.wait_for_function("() => document.fonts && document.fonts.status "
                             "=== 'loaded'", timeout=ms * 4)
    except Exception:                                       # noqa: BLE001
        # No webfonts, or they failed: measuring is still worth doing, and a
        # missing face is check_shell_consistency's business, not this one.
        pass
    pg.wait_for_timeout(400)


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
    for port in range(9101, 9151):
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
            for w in WIDTHS:
                rows = {}
                for p in PAGES:
                    ctx = b.new_context(viewport={"width": w, "height": 900})
                    pg = ctx.new_page()
                    pg.goto(base + p, wait_until="load", timeout=45000)
                    settle(pg)
                    rows[p] = pg.evaluate(PROBE)
                    ctx.close()

                ref_page = PAGES[0]
                ref = rows[ref_page]
                if ref is None:
                    problems.append("%dpx: no brand mark on %s" % (w, ref_page))
                    continue
                for p in PAGES[1:]:
                    r = rows[p]
                    if r is None:
                        problems.append("%dpx: no brand mark on %s" % (w, p))
                        continue
                    for key, label in (("markX", "mark x"), ("markY", "mark y"),
                                       ("markW", "mark width"),
                                       ("markH", "mark height"),
                                       ("gap", "gap to the wordmark"),
                                       ("nameX", "wordmark x"),
                                       ("nameW", "wordmark width")):
                        if abs(r[key] - ref[key]) > TOL:
                            problems.append(
                                "%dpx: %s differs on %s -- %.1f against %.1f on %s"
                                % (w, label, p, r[key], ref[key], ref_page))
                    for key, label in (("src", "image file"),
                                       ("radius", "corner radius"),
                                       ("nameFS", "wordmark font-size")):
                        if r[key] != ref[key]:
                            problems.append(
                                "%dpx: %s differs on %s -- %r against %r on %s"
                                % (w, label, p, r[key], ref[key], ref_page))
                print("    %4dpx  mark %.0fx%.0f at (%.0f,%.0f), gap %.1fpx, "
                      "wordmark %s"
                      % (w, ref["markW"], ref["markH"], ref["markX"],
                         ref["markY"], ref["gap"],
                         ref["nameFS"] if ref["nameShown"] else "hidden"))
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for x in problems[:12]:
            print("  - %s" % x)
        print("\n  The rule lives in five separate files. A value restated five")
        print("  times drifts, and a fraction of a pixel drifts unnoticed.")
        return 1
    print("  Mark and wordmark are identical on all %d pages, at %d widths."
          % (len(PAGES), len(WIDTHS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
