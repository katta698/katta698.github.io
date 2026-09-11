#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The footer's text must not sit underneath the floating buttons.

    python scripts/check_footer_clear.py
    python scripts/check_footer_clear.py --live

Why this exists
---------------
Two controls float over the bottom of every page on a phone: .back-top at the
bottom-left and .ask-launcher at the bottom-right. The footer's text has to
clear both.

It has failed this twice. The first time a rule left-aligned the footer and put
the copyright line and the palette toggle under the scroll-to-top button --
which made a control unpressable, not merely ugly. That was fixed with
symmetric padding, and the fix carried a comment explaining it.

Then a later rule, 150 lines further down and therefore winning, set
`padding: 2rem 4.25rem 2rem 1rem`: clearance on the right, 1rem on the left.
The same fault, reintroduced by a rule whose author had no reason to look 150
lines up. Nothing noticed, because nothing was looking -- it was found from a
photograph of a phone.

So this measures the rendered boxes rather than reading the CSS: where does the
footer's first line of text actually start, and where does the button actually
end. A rule can be overridden, but geometry cannot be argued with.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = [("portfolio", "/"), ("blog", "/blog/"),
         ("intelligence", "/intelligence/"),
         ("what's new", "/intelligence/whats-new/"),
         ("live status", "/intelligence/status/"),
         ("a post", "/blog/why-i-started-jayanthkatta-com/")]
WIDTHS = [320, 390, 412, 768]
# Both engines: this is a layout check, and layout is exactly where Safari and
# Chrome differ. The fault this file exists for was reported from a phone and
# reproduced in neither engine at first.
ENGINES = [("chromium", "Chrome / Edge"), ("webkit", "Safari, iPad, iPhone")]

# Every floating control that shares the bottom of the screen with the footer.
FLOATERS = ".back-top, .ask-launcher, .to-src, .fb-btn"

def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(8751, 8801):
        try:
            srv = socketserver.TCPServer(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


JS = """(sel) => {
  const f = document.querySelector('footer.site-footer');
  if (!f) return { none: true };
  const range = document.createRange();
  range.selectNodeContents(f);
  const t = range.getBoundingClientRect();
  const out = [];
  document.querySelectorAll(sel).forEach(e => {
    const s = getComputedStyle(e);
    if (s.display === 'none' || s.visibility === 'hidden') return;
    if (parseFloat(s.opacity) === 0) return;
    const r = e.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) return;
    out.push({ cls: (e.className || '').toString().split(' ')[0] || e.tagName,
               left: Math.round(r.left), right: Math.round(r.right) });
  });
  return { text: [Math.round(t.left), Math.round(t.right)], floaters: out };
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    os.chdir(ROOT)

    srv = None
    if args.live:
        base = "https://jayanthkatta.com"
    else:
        srv, port = serve()
        base = "http://127.0.0.1:%d" % port

    from playwright.sync_api import sync_playwright

    problems = []
    try:
        with sync_playwright() as pw:
          for engine, elabel in ENGINES:
            print("  %s" % elabel)
            b = getattr(pw, engine).launch()
            for name, path in PAGES:
                worst = None
                for w in WIDTHS:
                    pg = b.new_page(viewport={"width": w, "height": 860})
                    pg.goto(base + path, wait_until="networkidle", timeout=90000)
                    pg.wait_for_timeout(1600)
                    pg.evaluate("()=>window.scrollTo(0, document.body.scrollHeight)")
                    pg.wait_for_timeout(700)
                    r = pg.evaluate(JS, FLOATERS)
                    pg.close()
                    if r.get("none"):
                        problems.append("%s has no footer" % name)
                        continue
                    tl, tr = r["text"]
                    for fl in r["floaters"]:
                        # Horizontal overlap is what matters: these controls sit
                        # at the same height as the footer's last line.
                        if fl["right"] > tl and fl["left"] < tr:
                            gap = min(fl["right"] - tl, tr - fl["left"])
                            problems.append(
                                "%s, %s at %dpx: footer text runs under %s by %dpx"
                                % (elabel, name, w, fl["cls"], gap))
                            worst = (w, fl["cls"], gap)
                print("    %-13s %s" % (name, "ok" if not worst else
                                        "FAIL at %dpx under %s by %dpx" % worst))
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d OVERLAP(S)\n" % len(problems))
        for p in problems[:14]:
            print("  - %s" % p)
        print("\n  A control sitting on the footer's text is not only untidy:")
        print("  where the text is itself a link, it cannot be pressed.")
        return 1
    print("  the footer's text clears every floating control, on %d pages at"
          % len(PAGES))
    print("  %d widths." % len(WIDTHS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
