#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A feed opens in the theme the reader is already in.

    python scripts/check_feed_theme.py
    python scripts/check_feed_theme.py --live

Why this exists
---------------
Reported as: "I'm in light mode. So when I click on it, it goes to dark mode."

The feeds are XML with an XSLT stylesheet, and they load status.css, which
declares the dark palette on :root and the light one on body.light. Nothing
put that class on, so every feed opened dark whatever the reader had chosen.

This sat as "XSLT can't read the saved theme, OS-preference is the only
workable option" for a long time, and that was simply wrong. It was never
tested. A script in the XSLT output does run -- measured in both Chromium
and WebKit -- and the feed is same-origin, so localStorage holds the same
'theme' key the rest of the site uses. The feed can match the site exactly
rather than approximately, which matters because prefers-color-scheme would
have been wrong for precisely the reader who reported this: light site, and
whatever the OS happens to say.

So this checks the three states that exist, on every feed:

    saved 'light'  -> body.light, light ground
    saved 'dark'   -> no class, dark ground
    nothing saved  -> dark, which is the site default

Firefox is not driven here. Playwright's Firefox times out loading an XML
document in this harness -- the same class of quirk as WebKit hanging on
wait_until="load" -- and a check that cannot load the page cannot report
anything useful about it. That is a gap in the check, not a claim about the
browser, and it is written down rather than left implied.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEEDS = ["/intelligence/status/feed.xml", "/intelligence/status/feed-aws.xml",
         "/intelligence/status/feed-azure.xml", "/intelligence/status/feed-gcp.xml",
         "/blog/rss.xml"]

# (saved value, expected body class, expected to be the light ground)
CASES = [("light", "light", True), ("dark", "", False), (None, "", False)]

LIGHT_BG = "rgb(247, 244, 239)"
DARK_BG = "rgb(31, 29, 27)"

STATE = """() => ({
  transformed: !!document.querySelector('h1'),
  cls: document.body ? document.body.className.trim() : '(no body)',
  bg: document.body ? getComputedStyle(document.body).backgroundColor : '-'
})"""


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

        # Served as XML, or the browser renders the markup as text and the
        # stylesheet never runs -- which would make this check pass on a
        # page no reader ever sees.
        def guess_type(self, path):
            if path.endswith(".xml"):
                return "application/xml"
            if path.endswith(".xsl"):
                return "application/xslt+xml"
            return http.server.SimpleHTTPRequestHandler.guess_type(self, path)

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(9931, 9981):
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
            for engine in ("chromium", "webkit"):
                b = getattr(pw, engine).launch()
                print("  %s" % engine)
                for saved, want_cls, want_light in CASES:
                    bad = []
                    for f in FEEDS:
                        ctx = b.new_context(viewport={"width": 1440, "height": 900})
                        if saved:
                            ctx.add_init_script(
                                "try{localStorage.setItem('theme','%s');}"
                                "catch(e){}" % saved)
                        pg = ctx.new_page()
                        try:
                            pg.goto(base + f, wait_until="domcontentloaded",
                                    timeout=60000)
                            pg.wait_for_timeout(1500)
                            s = pg.evaluate(STATE)
                            # One retry, for the cold start only.
                            #
                            # The very first request of a run raced the local
                            # server coming up and came back untransformed --
                            # once, on the first feed, and never again in the
                            # run or on a re-run. Reloading costs a second and
                            # keeps a real failure reportable; a gate that
                            # cries wolf on its first line is a gate nobody
                            # reads past.
                            if not s["transformed"]:
                                pg.reload(wait_until="domcontentloaded",
                                          timeout=60000)
                                pg.wait_for_timeout(2000)
                                s = pg.evaluate(STATE)
                        except Exception as exc:              # noqa: BLE001
                            problems.append("%s %s (saved=%s): could not load "
                                            "(%s)" % (engine, f, saved,
                                                      str(exc)[:40]))
                            ctx.close()
                            continue
                        ctx.close()
                        if not s["transformed"]:
                            problems.append(
                                "%s %s: the stylesheet did not run -- this is "
                                "raw XML to a reader" % (engine, f))
                            bad.append(f)
                            continue
                        want_bg = LIGHT_BG if want_light else DARK_BG
                        if s["cls"] != want_cls or s["bg"] != want_bg:
                            problems.append(
                                "%s %s (saved=%s): body class %r on %s, wanted "
                                "%r on %s" % (engine, f, saved, s["cls"],
                                              s["bg"], want_cls, want_bg))
                            bad.append(f)
                    print("     saved=%-5s %s"
                          % (str(saved),
                             "all %d feeds %s" % (len(FEEDS),
                                                  "light" if want_light else "dark")
                             if not bad else "%d WRONG" % len(bad)))
                b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for x in problems[:12]:
            print("  - %s" % x)
        print("\n  A feed that opens dark for a reader in light mode is the")
        print("  site contradicting itself one click outside itself.")
        return 1
    print("  Feeds follow the saved theme: %d feeds, %d states, 2 engines."
          % (len(FEEDS), len(CASES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
