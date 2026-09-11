#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the map on every engine and screen size, and check it still works.

    python scripts/check_map_devices.py
    python scripts/check_map_devices.py --shots

Why this exists
---------------
The pulse that marks a live incident was written and checked in Chromium, and
on an iPad it did not move. Two reasons, both invisible from the desktop: the
keyframe animated the SVG `r` property, which is the corner of CSS animation
WebKit is least consistent about, and it carried a leftover that reset every
ring to the same radius on each repeat. Nothing about the Chromium render
suggested either.

"Looks fine on my machine" is not a test when the thing being checked is an
alarm. This drives the real WebKit and Gecko engines at phone, tablet and
desktop widths and asks the page itself what it is doing: are the animations
running, is the alert strip there, did the dots draw, does anything overflow
its viewport.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8931
URL_TEMPLATE = "http://127.0.0.1:%d/intelligence/status/"

DEVICES = [
    ("phone",   390, 844),
    ("tablet",  834, 1112),      # iPad portrait
    ("tablet-l", 1112, 834),     # iPad landscape
    ("desktop", 1440, 900),
]

PROBE = """() => {
  const q = s => document.querySelectorAll(s).length;
  const pulses = [...document.querySelectorAll('.om-pulse')];
  const running = 0;
  const pulseAnimated = 0;
  const svg = document.querySelector('.om-svg');
  const box = svg ? svg.getBoundingClientRect() : null;
  return {
    dots: q('.om-dot'),
    circles: q('.om-svg .om-pie circle'),
    wedges: q('.om-svg .om-pie path'),
    hits: q('.om-hit'),
    pulses: pulses.length,
    pulseAnimated: pulseAnimated,
    running: running,
    alert: q('.om-alert'),
    jumps: q('.om-jump'),
    keys: q('.om-key li'),
    labels: q('.om-names text'),
    svgW: box ? Math.round(box.width) : 0,
    overflow: Math.round(document.documentElement.scrollWidth) >
              Math.round(document.documentElement.clientWidth) + 1
  };
}"""


def _serve(handler, port):
    """A local server on `port`, or the next free one after it.

    Every one of these checks hardcodes a port, and a run that is interrupted
    leaves the socket held -- so the next run dies with WinError 10048 and
    reports nothing at all. That is worse than a failure: a check that cannot
    start looks exactly like a check that was not run, and it cost several
    rounds today at exactly the moment the answer mattered.
    """
    import socketserver as _ss
    _ss.TCPServer.allow_reuse_address = True
    for p in range(port, port + 40):
        try:
            return _ss.TCPServer(("127.0.0.1", p), handler), p
        except OSError:
            continue
    raise SystemExit("no free port in %d-%d" % (port, port + 40))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", action="store_true")
    args = ap.parse_args()

    os.chdir(ROOT)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    srv, PORT_USED = _serve(Quiet, PORT)
    URL = URL_TEMPLATE % PORT_USED
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    from playwright.sync_api import sync_playwright

    problems = []
    with sync_playwright() as pw:
        for engine in ("chromium", "webkit", "firefox"):
            try:
                browser = getattr(pw, engine).launch()
            except Exception as exc:                            # noqa: BLE001
                print("  %-9s unavailable (%s)" % (engine, str(exc)[:50]))
                continue
            for name, w, h in DEVICES:
                pg = browser.new_page(viewport={"width": w, "height": h})
                errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(URL, wait_until="networkidle", timeout=60000)
                try:
                    pg.wait_for_selector(".om-pie", timeout=25000)
                except Exception:                               # noqa: BLE001
                    problems.append("%s/%s: the map never drew" % (engine, name))
                    pg.close()
                    continue
                pg.wait_for_timeout(1500)
                r = pg.evaluate(PROBE)
                # Does the alarm actually MOVE? Measured, not asked.
                #
                # getAnimations() does not report SVG's own <animate>, and
                # the earlier version of this check asked the browser whether
                # an animation object existed rather than whether anything
                # changed on screen -- which is how an animation that ran and
                # was invisible passed. This samples the ring's drawn radius
                # and looks at the spread.
                if r["pulses"]:
                    widths = []
                    for _ in range(12):
                        widths.append(pg.evaluate(
                            "() => {const p=document.querySelector('.om-pulse');"
                            "return p ? p.getBoundingClientRect().width : 0;}"))
                        pg.wait_for_timeout(180)
                    lo, hi = min(widths), max(widths)
                    r["grow"] = round(hi / lo, 2) if lo > 0.5 else 0
                tag = "%s/%s" % (engine, name)
                print("  %-18s dots %2d  circles %2d  wedges %3d  pulses %d "
                      "(grows %sx)  alert %d  labels %2d  svg %4dpx%s"
                      % (tag, r["dots"], r["circles"], r["wedges"], r["pulses"],
                         r.get("grow", "-"), r["alert"], r["labels"], r["svgW"],
                         "  OVERFLOW" if r["overflow"] else ""))
                if not r["dots"]:
                    problems.append("%s: no dots drew" % tag)
                # A ring that never changes size is a static ring, whatever
                # the browser says about animation objects existing.
                if r["pulses"] and r.get("grow", 0) < 1.5:
                    problems.append(
                        "%s: the live ring barely moves (grows %sx, want 1.5x+)"
                        % (tag, r.get("grow")))
                if r["overflow"]:
                    problems.append("%s: the page scrolls sideways" % tag)
                # Expanding the map must actually make the map bigger.
                #
                # Fitting the whole world into the screen was the obvious
                # reading and gained four per cent on a phone -- a 2:1 map in a
                # 1:2 viewport letterboxes, so "maximise" returned very nearly
                # what was already there. It fills the height and pans sideways
                # instead, which is several times the area. A button that
                # appears to do nothing is worse than no button, so the gain is
                # measured rather than assumed.
                if pg.query_selector("#om-expand"):
                    before = pg.evaluate(
                        "() => {const s=document.querySelector('.om-svg');"
                        "const b=s.getBoundingClientRect();"
                        "return Math.round(b.width*b.height);}")
                    pg.click("#om-expand")
                    pg.wait_for_timeout(600)
                    after = pg.evaluate(
                        "() => {const s=document.querySelector('.om-svg');"
                        "const b=s.getBoundingClientRect();"
                        "return Math.round(b.width*b.height);}")
                    closed = pg.query_selector(".om-close") is not None
                    pg.keyboard.press("Escape")
                    pg.wait_for_timeout(400)
                    still = pg.evaluate(
                        "() => document.getElementById('outage-map')"
                        ".classList.contains('is-big')")
                    grew = round(after / max(1, before), 1)
                    if grew < 2:
                        problems.append(
                            "%s: expanding the map gained only %sx the area"
                            % (tag, grew))
                    if not closed:
                        problems.append("%s: expanded with no way to close it" % tag)
                    if still:
                        problems.append("%s: Escape did not close the expanded map"
                                        % tag)

                if errs:
                    problems.append("%s: console error %s" % (tag, errs[0][:70]))
                if args.shots:
                    pg.screenshot(path="map-%s-%s.png" % (engine, name),
                                  full_page=False)
                pg.close()

            # And the same page for a reader who has asked for less motion.
            #
            # This is not a hypothetical: the report that the alarm was static
            # on an iPad turned out to be Reduce Motion, which also froze the
            # lamp on the front page. Under that setting the ring must not
            # move -- movement across the screen is the thing the setting
            # exists to stop -- but it must still be distinguishable from a
            # region that broke last week, so it breathes instead. Both
            # halves of that are checked.
            pg = browser.new_page(viewport={"width": 834, "height": 1112},
                                  reduced_motion="reduce")
            pg.goto(URL, wait_until="networkidle", timeout=60000)
            try:
                pg.wait_for_selector(".om-pulse", timeout=25000)
            except Exception:                                   # noqa: BLE001
                problems.append("%s/reduced-motion: no alarm ring at all" % engine)
                pg.close()
                browser.close()
                continue
            pg.wait_for_timeout(600)
            ws, ops = [], []
            for _ in range(12):
                pair = pg.evaluate(
                    "() => {const p=document.querySelector('.om-pulse');"
                    "return [p.getBoundingClientRect().width,"
                    "parseFloat(getComputedStyle(p).opacity)];}")
                ws.append(pair[0])
                ops.append(pair[1])
                pg.wait_for_timeout(190)
            moved = max(ws) / max(min(ws), 0.1)
            breath = max(ops) - min(ops)
            print("  %-18s ring holds still (%.2fx) and breathes (%.2f opacity "
                  "swing)" % ("%s/reduced" % engine, moved, breath))
            if moved > 1.15:
                problems.append("%s/reduced-motion: the ring still moves %.2fx"
                                % (engine, moved))
            if breath < 0.15:
                problems.append(
                    "%s/reduced-motion: the alarm is indistinguishable from a "
                    "past incident (opacity swing %.2f)" % (engine, breath))
            pg.close()
            browser.close()
    srv.shutdown()

    if problems:
        print("\n  %d PROBLEM(S)\n" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("\n  the map draws and animates on every engine and size tested.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
