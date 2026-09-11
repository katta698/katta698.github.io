#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The feedback widget must answer the same gesture the same way on every page.

    python scripts/check_feedback.py
    python scripts/check_feedback.py --live      # against jayanthkatta.com

Why this exists
---------------
The widget existed as four inline copies -- one in index.html, one in
intelligence/index.html, one emitted by sync_blog.py into every post, one in
feedback_star.py for the Intelligence pages -- and they had drifted:

    Escape closed it     on the 3 Intelligence pages, not on portfolio or blog
    backdrop closed it   on blog and status, not on portfolio
    scroll locked        on portfolio only

So the same modal answered the same gesture three different ways depending on
which page you were standing on. On the portfolio it could not be dismissed at
all except by finding the Skip button, which is the sort of thing a reader
blames the site for rather than reports.

None of that is visible from looking at a page. Each copy worked; they simply
did not agree. Copies drift -- that is what they do -- so the behaviour now
lives in one file, and this asserts that every page actually got it.
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
         ("live status", "/intelligence/status/")]
# One post as well: 223 of them are generated from a single template, so if the
# template is right they are all right -- but nothing had been checking that
# the template is right.
PAGES.append(("a blog post", "/blog/why-i-started-jayanthkatta-com/"))


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(8811, 8861):
        try:
            srv = socketserver.TCPServer(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


def probe(page, url, engine="chromium"):
    """Open the modal and try every way a person would expect to close it.

    In both engines. Escape, scroll locking and focus behaviour are exactly the
    kind of thing browsers disagree about -- Chrome clears a type="search" input
    on Escape and WebKit does not, which is how one key came to do two different
    things on the region search. A modal checked in one engine is a modal
    checked for half the readers.
    """
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as pw:
        b = getattr(pw, engine).launch()
        pg = b.new_page(viewport={"width": 390, "height": 844})
        pg.goto(url, wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(1600)

        out["button"] = bool(pg.query_selector(".fb-btn"))
        if not out["button"]:
            b.close()
            return out

        # The hit area, which is what a thumb actually lands on.
        out["hit"] = pg.evaluate("""()=>{const b=document.querySelector('.fb-btn');
          const a=getComputedStyle(b,'::after');
          const w=parseFloat(a.width)||b.getBoundingClientRect().width;
          const h=parseFloat(a.height)||b.getBoundingClientRect().height;
          return Math.round(Math.min(w,h));}""")

        pg.click(".fb-btn")
        pg.wait_for_timeout(500)
        out["opens"] = pg.evaluate("()=>!!document.querySelector('.fb-overlay.open')")
        out["dialog"] = pg.evaluate("""()=>{const m=document.querySelector('.fb-modal');
          return !!(m && m.getAttribute('role')==='dialog'
                    && m.getAttribute('aria-modal')==='true'
                    && (m.getAttribute('aria-label')||m.getAttribute('aria-labelledby')));}""")
        out["locked"] = pg.evaluate(
            "()=>getComputedStyle(document.body).overflow==='hidden'")
        out["focus_in"] = pg.evaluate("""()=>{const o=document.querySelector('.fb-overlay');
          return !!(o && o.contains(document.activeElement));}""")

        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)
        out["escape"] = not pg.evaluate(
            "()=>!!document.querySelector('.fb-overlay.open')")
        out["unlocked"] = pg.evaluate(
            "()=>getComputedStyle(document.body).overflow!=='hidden'")

        # And the backdrop, on a fresh open.
        pg.click(".fb-btn")
        pg.wait_for_timeout(400)
        pg.mouse.click(195, 60)
        pg.wait_for_timeout(400)
        out["backdrop"] = not pg.evaluate(
            "()=>!!document.querySelector('.fb-overlay.open')")
        b.close()
    return out


WANT = [("opens", "opens"), ("escape", "Escape closes"),
        ("backdrop", "backdrop closes"), ("locked", "scroll locked"),
        ("unlocked", "scroll released"), ("dialog", "announced as a dialog"),
        ("focus_in", "focus moves in")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="check the deployed site instead of this checkout")
    args = ap.parse_args()

    os.chdir(ROOT)
    srv = None
    if args.live:
        base = "https://jayanthkatta.com"
    else:
        srv, port = serve()
        base = "http://127.0.0.1:%d" % port

    bad = []
    try:
        for engine, label in (("chromium", "Chrome / Edge"),
                              ("webkit", "Safari, iPad and iPhone")):
            print("  %s" % label)
            for name, path in PAGES:
                r = probe(name, base + path, engine)
                if not r.get("button"):
                    bad.append("%s in %s has no feedback button" % (name, label))
                    print("    %-13s NO BUTTON" % name)
                    continue
                missing = [lab for key, lab in WANT if not r.get(key)]
                hit = r.get("hit") or 0
                if hit < 24:
                    missing.append("hit area only %dpx" % hit)
                for m in missing:
                    bad.append("%s in %s: %s" % (name, label, m))
                print("    %-13s %-4s hit %dpx  %s"
                      % (name, "ok" if not missing else "FAIL", hit,
                         "" if not missing else "— missing: " + ", ".join(missing)))
    finally:
        if srv:
            srv.shutdown()

    print()
    if bad:
        print("  %d DISAGREEMENT(S) BETWEEN PAGES\n" % len(bad))
        for x in bad:
            print("  - %s" % x)
        print("\n  The same widget answering the same gesture differently is")
        print("  how a reader learns not to trust the controls.")
        return 1
    print("  every page opens, closes on Escape, closes on the backdrop, locks")
    print("  the page behind it, announces itself as a dialog and takes focus")
    print("  — %d pages, identically." % len(PAGES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
