#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The floating controls exist, and are not swallowed by something hidden.

    python scripts/check_post_controls.py
    python scripts/check_post_controls.py --live

Why this exists
---------------
Reported as icons missing from the posts published on 13 and 14 September --
among them the up arrow. They were in the HTML on every page and invisible on
seventeen of them, because their PARENT was wrong:

    working page   .ask-launcher  parent body        52x52
    broken page    .ask-launcher  parent div.fb-modal  0x0

The feedback modal is hidden until someone opens it. Anything that ends up
inside it is hidden too, at zero size, while still being present in the
markup and still reporting display:flex and opacity:1. Nothing looked wrong
from the element's own properties; only its parent gave it away.

The cause was two missing </div> and a stray '<':

    good    </div>  </div>  <script src=".../feedback.js?v=X" defer></script>
    broken  </div>  <<script src=".../feedback.js?v=X" defer></script>();  </script>

which left the modal unclosed, so it adopted every element after it. The
trailing "();  </script>" is debris from the Disqus block above it -- a bulk
edit had eaten a run of text across the boundary. Seventeen pages carried it.

This checks the property that failed, not the text that caused it: each
control must be a direct child of <body> and must have a real size. A static
search for that exact broken string would only ever find this one accident;
any future edit that reparents these controls produces the same invisible
result by a different route.

Pages are sampled rather than exhaustive -- there are 248 and they come from
one template. --live checks production instead of the working copy.
"""
import argparse
import http.server
import io
import json
import os
import random
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = 12
CONTROLS = [(".ask-launcher", "ask button", 30),
            (".back-top", "back-to-top arrow", 24),
            (".fb-btn", "feedback star", 24)]

PROBE = """(sels) => {
  const out = {};
  sels.forEach(function (s) {
    const e = document.querySelector(s);
    if (!e) { out[s] = {missing: true}; return; }
    const r = e.getBoundingClientRect();
    out[s] = {
      parent: e.parentElement ? e.parentElement.tagName.toLowerCase() : '(none)',
      parentClass: e.parentElement ? (e.parentElement.className || '').toString() : '',
      w: Math.round(r.width), h: Math.round(r.height)
    };
  });
  return out;
}"""


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
    for port in range(9401, 9451):
        try:
            srv = _Threaded(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


def slugs():
    cards = json.load(io.open(os.path.join(ROOT, "blog", "cards.json"),
                              encoding="utf-8"))
    items = cards if isinstance(cards, list) else cards.get("cards", [])
    names = [c["slug"] for c in items if c.get("slug")]
    random.seed(0)                      # same sample every run, so it is comparable
    return sorted(random.sample(names, min(SAMPLE, len(names))))


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
    checked = 0
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            ctx = b.new_context(viewport={"width": 390, "height": 844})
            pg = ctx.new_page()
            for slug in slugs():
                pg.goto("%s/blog/%s/" % (base, slug),
                        wait_until="load", timeout=60000)
                pg.wait_for_timeout(2200)
                # the arrow only shows once there is somewhere to go back to
                pg.evaluate("() => window.scrollTo(0, 1500)")
                pg.wait_for_timeout(800)
                found = pg.evaluate(PROBE, [c[0] for c in CONTROLS])
                checked += 1
                worst = []
                for sel, label, floor in CONTROLS:
                    r = found[sel]
                    if r.get("missing"):
                        problems.append("%s: %s is not on the page" % (slug, label))
                        worst.append(label + " missing")
                        continue
                    if r["parent"] != "body":
                        problems.append(
                            "%s: %s sits inside <%s class=%r> instead of <body> "
                            "-- it is present but hidden, at %dx%d"
                            % (slug, label, r["parent"], r["parentClass"][:24],
                               r["w"], r["h"]))
                        worst.append("%s in %s" % (label, r["parent"]))
                    elif r["w"] < floor or r["h"] < floor:
                        problems.append(
                            "%s: %s renders %dx%d, under %dpx"
                            % (slug, label, r["w"], r["h"], floor))
                        worst.append("%s %dx%d" % (label, r["w"], r["h"]))
                print("    %-46s %s" % (slug[:46], "; ".join(worst) or "ok"))
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S) across %d page(s)\n" % (len(problems), checked))
        for x in problems[:12]:
            print("  - %s" % x)
        print("\n  A control adopted by a hidden parent still reports")
        print("  display:flex and opacity:1. Only its parent gives it away.")
        return 1
    print("  All three controls are attached to <body> and visible, on %d "
          "sampled posts." % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
