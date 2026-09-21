#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nothing in the walkthrough is drawn underneath its own controls.

    python scripts/check_player_overlays.py
    python scripts/check_player_overlays.py --live

Why this exists
---------------
Reported with a screenshot, and the whole report was two words: "Anything
off". In it, the "Intelligence" box in scene 7 was sitting behind the CC and
mute buttons.

It was not one label and it was not one scene. The artwork filled the entire
frame and the control bar is an overlay across the bottom of it, so on EVERY
scene the lowest band of the picture was underneath the controls -- and the
caption, a second overlay, covered another strip above that. Measured against
the bar's own rectangle before the fix:

    412px    37px of artwork covered
    390px    37px
   1180px    39px, including the words "one file, by hand"

None of this is visible to any check that reads markup or CSS. The elements
are all present, all styled, all "visible" by every usual definition. They are
simply painted under something opaque, which is a question only geometry can
answer: does the rectangle of a drawn thing intersect the rectangle of an
overlay that is on top of it?

So that is the question this asks, for all eight scenes, at four widths, with
subtitles both ON and OFF -- because the caption reserve is conditional and
"off" is the case where the drawing is allowed to take the whole frame.

It steps scenes by clicking the scrub bar at real coordinates rather than
dispatching an input event. A dispatched event bypasses hit testing entirely,
which is how a 4px-tall scrub bar passed as working while nobody could
actually grab it.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGE = "/how-this-was-made/"

# Phone, phone, small phone, laptop. The caption reserve differs across the
# media query, so both sides of it are measured.
WIDTHS = [(412, 915, "android"), (390, 844, "iphone"),
          (360, 800, "small"), (1180, 900, "desktop")]

SCENES = 8

# A few pixels of a stroke's antialiasing touching a scrim is not a defect.
# 4px is under one line of text at any size this page uses.
TOLERANCE = 4

# The active scene's drawn elements, against every overlay above them.
PROBE = """
(tol) => {
  const on = document.querySelector('.sc.is-on');
  if (!on) return 'NO ACTIVE SCENE';
  const covers = [];
  const bar = document.querySelector('.cf-bar');
  if (bar) covers.push(['controls', bar.getBoundingClientRect()]);
  const cap = document.querySelector('.cf-cap');
  if (cap && getComputedStyle(cap).opacity !== '0'
      && (cap.textContent || '').trim()) {
    const span = cap.querySelector('span');
    covers.push(['caption', (span || cap).getBoundingClientRect()]);
  }
  let worst = 0, label = '', who = '';
  on.querySelectorAll('text,rect,circle,path,line').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;
    covers.forEach(([nm, b]) => {
      const oy = Math.min(r.bottom, b.bottom) - Math.max(r.top, b.top);
      const ox = Math.min(r.right, b.right) - Math.max(r.left, b.left);
      if (oy > tol && ox > tol && oy > worst) {
        worst = oy; who = nm;
        label = e.tagName === 'text'
          ? '"' + (e.textContent || '').trim().slice(0, 24) + '"'
          : '<' + e.tagName + '>';
      }
    });
  });
  return worst ? (Math.round(worst) + 'px of ' + label + ' under the ' + who)
               : null;
}
"""


class _Threaded(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


# The page's own blocks, laid out beside each other rather than on top.
#
# Reported from a phone: one stat card showing seven numbers printed over
# each other and every label overlapping. The cause was a class name used
# by two unrelated components in two different files -- .cf-num is a stat
# card here and was also the trip's step number, so a 560px rule written
# for the step number put all seven cards in grid cell 1/1.
#
# Neither file looked wrong when read on its own, both components existed,
# every element was "visible", and the markup was valid. Only the geometry
# says anything. This is the same question the scene probe above asks, put
# to the page instead of to the artwork: are two things that should sit
# beside each other occupying the same place?
STACKED = """(sel) => {
  const out = [];
  document.querySelectorAll(sel).forEach(parent => {
    const kids = [...parent.children].filter(k => {
      const r = k.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    });
    const seen = new Map();
    kids.forEach(k => {
      const r = k.getBoundingClientRect();
      const key = Math.round(r.left) + ',' + Math.round(r.top);
      if (seen.has(key)) {
        const label = (k.textContent || '').trim().replace(/\s+/g, ' ');
        out.push((parent.className || parent.tagName) + ': '
                 + label.slice(0, 30) + ' is drawn on top of '
                 + (seen.get(key) || '').slice(0, 30));
      } else {
        seen.set(key, (k.textContent || '').trim()
                        .replace(/\s+/g, ' '));
      }
    });
  });
  return out; }"""

# Containers whose children are meant to sit side by side or stacked in a
# list -- never in the same place. The scenes are deliberately layered and
# are covered by the probe above, so they are not in this list.
ROWS = ".cf-nums, .cf-trip-paths, .cf-trip, .cf-flow, .cf-parts dl"


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    for port in range(9760, 9800):
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
            br = pw.chromium.launch(
                args=["--autoplay-policy=no-user-gesture-required"])
            for width, height, wname in WIDTHS:
                for cc_on in (True, False):
                    ctx = br.new_context(viewport={"width": width,
                                                   "height": height},
                                         has_touch=width < 500,
                                         is_mobile=width < 500)
                    pg = ctx.new_page()
                    pg.goto(base + PAGE, wait_until="load", timeout=90000)
                    pg.wait_for_timeout(1500)
                    pg.locator(".cf-player").scroll_into_view_if_needed()
                    pg.wait_for_timeout(300)
                    pg.locator(".cf-big").click()
                    pg.wait_for_timeout(900)

                    want = "true" if cc_on else "false"
                    if pg.get_attribute("[data-journey-cc]",
                                        "aria-pressed") != want:
                        pg.locator("[data-journey-cc]").click()
                        pg.wait_for_timeout(400)
                    # Pause, then step scene by scene: a moving picture
                    # measured mid-transition reports its own fade, not a
                    # layout fault.
                    pg.locator("[data-journey-play]").click()

                    bad = []
                    for i in range(SCENES):
                        box = pg.locator("[data-seek]").bounding_box()
                        x = box["x"] + 4 + (box["width"] - 8) * (
                            i / float(SCENES - 1))
                        pg.mouse.click(x, box["y"] + box["height"] / 2)
                        pg.wait_for_timeout(650)
                        hit = pg.evaluate(PROBE, TOLERANCE)
                        if hit:
                            bad.append("scene %d: %s" % (i + 1, hit))

                    stacked = pg.evaluate(STACKED, ROWS)
                    if stacked:
                        bad.append("%d block(s) stacked: %s"
                                   % (len(stacked), stacked[0]))
                        for hit in stacked:
                            problems.append("%dpx: %s" % (width, hit))

                    print("  %-8s %4dpx  CC %-3s  %s"
                          % (wname, width, "on" if cc_on else "off",
                             "all %d scenes clear" % SCENES if not bad
                             else bad[0]))
                    for b in bad:
                        problems.append("%s at %dpx with subtitles %s -- %s"
                                        % (wname, width,
                                           "on" if cc_on else "off", b))
                    ctx.close()
            br.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d THING(S) DRAWN UNDER AN OVERLAY" % len(problems))
        print()
        for p in problems[:10]:
            print("  - %s" % p)
        if len(problems) > 10:
            print("  ...and %d more" % (len(problems) - 10))
        print()
        print("  Every one of those elements is present, styled and visible.")
        print("  They are painted underneath something opaque, which only")
        print("  geometry can see.")
        return 1
    print("  All %d scenes clear of the controls and the caption, at %d "
          "widths,\n  with subtitles on and off." % (SCENES, len(WIDTHS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
