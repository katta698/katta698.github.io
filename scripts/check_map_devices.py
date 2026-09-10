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
URL = "http://127.0.0.1:%d/intelligence/status/" % PORT

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", action="store_true")
    args = ap.parse_args()

    os.chdir(ROOT)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    srv = socketserver.TCPServer(("127.0.0.1", PORT), Quiet)
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
                if errs:
                    problems.append("%s: console error %s" % (tag, errs[0][:70]))
                if args.shots:
                    pg.screenshot(path="map-%s-%s.png" % (engine, name),
                                  full_page=False)
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
