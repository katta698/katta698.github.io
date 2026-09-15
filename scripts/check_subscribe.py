#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The subscribe control opens something, on every page and both sizes.

    python scripts/check_subscribe.py
    python scripts/check_subscribe.py --live

Why this exists
---------------
Reported as: "the subscribe button doesn't work. It still exists, but when I
click it, it doesn't show me anything."

The button was created by site-footer.js, which opened with

    if (!nav || nav.querySelector('.subnav-btn')) return;

-- correct while the script was the only thing that made one. Then the button
moved into each page's markup, to stop it arriving after first paint and
blinking, and that guard began matching on every page. The script returned
immediately, so the panel was never built and no click handler was ever
attached. A button that is present, correctly styled, correctly placed, and
inert.

Nothing else could see it. The button existed, so every check that asked
whether it existed passed. check_shell_consistency measured its size, position,
background and border and found all five pages identical -- which they were.
The one thing nobody asked was whether pressing it did anything.

So this presses it. On the desktop it presses the glyph in the bar; on a phone
it opens the menu and presses the row inside, because the glyph is hidden at
that width. It then requires the panel to be open AND to contain the email
field, because an empty panel would satisfy a weaker test and is the failure
mode this has already had once.
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

OPEN = """() => {
  const p = document.getElementById('sub-panel');
  if (!p) return {panel: false};
  return {
    panel: !p.hidden,
    email: !!p.querySelector('#subnav-email'),
    feeds: p.querySelectorAll('.sub-list li').length
  };
}"""


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(9501, 9551):
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
            for width, how in ((1440, "the glyph in the bar"),
                               (390, "the row in the menu")):
                ctx = b.new_context(viewport={"width": width, "height": 900})
                pg = ctx.new_page()
                for p in PAGES:
                    pg.goto(base + p, wait_until="load", timeout=60000)
                    pg.wait_for_timeout(2500)
                    try:
                        if width >= 1081:
                            pg.click("#subnav-btn", timeout=5000)
                        else:
                            pg.click("#ck-btn", timeout=5000)
                            pg.wait_for_timeout(400)
                            pg.click(".ck-sub-open", timeout=5000)
                        pg.wait_for_timeout(700)
                    except Exception as exc:                   # noqa: BLE001
                        problems.append("%s at %dpx: could not press %s (%s)"
                                        % (p, width, how, str(exc)[:45]))
                        continue
                    r = pg.evaluate(OPEN)
                    if not r.get("panel"):
                        problems.append(
                            "%s at %dpx: pressed %s and nothing opened -- the "
                            "control is there and inert" % (p, width, how))
                    elif not r.get("email") or not r.get("feeds"):
                        problems.append(
                            "%s at %dpx: the panel opened but holds email=%s "
                            "feeds=%s" % (p, width, r.get("email"), r.get("feeds")))
                    else:
                        print("    %4dpx  %-26s opens, %d feed(s) and the "
                              "email field" % (width, p, r["feeds"]))
                ctx.close()
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for x in problems[:12]:
            print("  - %s" % x)
        print("\n  A control that exists, looks right and does nothing passes")
        print("  every check that only asks whether it is there.")
        return 1
    print("  Subscribe opens on all %d pages, at both sizes." % len(PAGES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
