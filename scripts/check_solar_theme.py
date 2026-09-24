#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The contact card follows the reader's own sunrise and sunset.

Asked for: "let mode change based on sunset and sunrise time in local
time zone wherever it is." So the page computes the solar times for the
device rather than asking the operating system which theme it prefers.

Three things can go wrong with that, and two of them already did:

  the longitude   is taken from the timezone's meridian, which is free and
                  needs no permission -- but in a daylight-saving zone the
                  CURRENT offset is an hour short, which would place a
                  reader in Chicago fifteen degrees east of where they are
                  and move sunset by an hour. The standard offset is used
                  instead, found by bracketing January and July.

  the day number  has to be the reader's day, not UTC's. Anchored to the
                  instant, 07:00 in Sydney is still yesterday in UTC, and
                  the page came up dark on a bright morning. Anchored to
                  local noon it is right. Invisible from anywhere near
                  Greenwich, which is how it nearly shipped.

  the poles       have days with no sunrise at all. The cosine of the hour
                  angle goes outside [-1, 1] there, and the answer is a
                  whole day of light or dark rather than a NaN.

So the clock and the timezone are both pinned, and the page is asked what
it shows in nine places around the world at moments where the answer is
not in doubt. Times within half an hour of published ones are accepted:
that is the timezone-meridian approximation, and it is the honest price
of not asking for the reader's location.
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("  playwright not installed -- skipping")
    sys.exit(0)

PORT = 9089
URL = "http://127.0.0.1:%d/connect/" % PORT

# label, timezone, the pinned instant (UTC), what the sky is doing there
CASES = [
    ("Chicago, midday", "America/Chicago", "2026-09-24T17:00:00Z", "light"),
    ("Chicago, night", "America/Chicago", "2026-09-25T03:00:00Z", "dark"),
    ("Kolkata, morning", "Asia/Kolkata", "2026-09-24T01:30:00Z", "light"),
    ("Kolkata, evening", "Asia/Kolkata", "2026-09-24T15:30:00Z", "dark"),
    ("London, June dusk", "Europe/London", "2026-06-21T19:30:00Z", "light"),
    ("London, December", "Europe/London", "2026-12-21T20:30:00Z", "dark"),
    ("Sydney, morning", "Australia/Sydney", "2026-09-23T21:00:00Z", "light"),
    ("Sydney, evening", "Australia/Sydney", "2026-09-24T10:00:00Z", "dark"),
    ("Los Angeles, June", "America/Los_Angeles", "2026-06-21T01:00:00Z", "light"),
]


def main():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                           cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    time.sleep(2)
    bad = []
    try:
        with sync_playwright() as p:
            b = p.webkit.launch()
            for label, tz, when, want in CASES:
                ctx = b.new_context(viewport={"width": 402, "height": 874},
                                    device_scale_factor=2, is_mobile=True,
                                    has_touch=True, timezone_id=tz)
                pg = ctx.new_page()
                pg.clock.install(time=when)
                pg.goto(URL, wait_until="domcontentloaded")
                pg.wait_for_timeout(1000)
                got = pg.evaluate("()=>document.documentElement.dataset.theme")
                local = pg.evaluate(
                    "()=>new Date().toLocaleString('en-GB',"
                    "{hour:'2-digit',minute:'2-digit'})")
                nxt = pg.evaluate("""()=>{
                    const s = window.JKSolar ? window.JKSolar() : null;
                    return s && s.next
                      ? new Date(s.next).toLocaleString('en-GB',
                          {hour:'2-digit',minute:'2-digit'})
                      : 'never'; }""")
                ok = got == want
                print("  %-19s %-20s %s  %-5s %-12s next %s"
                      % (label, tz, local, got,
                         "ok" if ok else "WANTED " + want, nxt))
                if not ok:
                    bad.append("%s: the card is %s at %s local, and the sun "
                               "says %s" % (label, got, local, want))
                ctx.close()

            # ---- a tap wins, and keeps winning --------------------------
            ctx = b.new_context(viewport={"width": 402, "height": 874},
                                device_scale_factor=2, is_mobile=True,
                                has_touch=True, timezone_id="America/Chicago")
            pg = ctx.new_page()
            pg.clock.install(time="2026-09-24T17:00:00Z")     # midday
            pg.goto(URL, wait_until="domcontentloaded")
            pg.wait_for_timeout(900)
            before = pg.evaluate("()=>document.documentElement.dataset.theme")
            box = pg.evaluate("""()=>{const r=document.getElementById('lamp')
                .getBoundingClientRect();
                return {x:Math.round(r.x+r.width/2),
                        y:Math.round(r.y+r.height/2)};}""")
            pg.touchscreen.tap(box["x"], box["y"])
            pg.wait_for_timeout(500)
            after = pg.evaluate("()=>document.documentElement.dataset.theme")
            stored = pg.evaluate(
                "()=>JSON.parse(localStorage.getItem('connect.theme')||'null')")
            pg.reload(wait_until="domcontentloaded")
            pg.wait_for_timeout(900)
            kept = pg.evaluate("()=>document.documentElement.dataset.theme")
            print("  a tap at midday: %s -> %s, still %s after a reload, "
                  "expires %s" % (before, after, kept,
                                  "at the next solar change"
                                  if stored and stored.get("until")
                                  else "never -- it holds until the next tap"))
            if after == before:
                bad.append("tapping the orb did not change the sheet")
            if kept != after:
                bad.append("the tapped choice did not survive a reload")
            # A tap is a decision and holds until the next tap. This was
            # the opposite for a day -- kept only until the next sunrise or
            # sunset -- and the assertion is inverted with it, deliberately,
            # so nobody "fixes" it back by accident.
            if stored is None or stored.get("t") != after:
                bad.append("the tapped choice was not recorded")
            if stored and stored.get("until"):
                bad.append("the tapped choice carries an expiry; it is meant "
                           "to hold until the reader taps again")
            ctx.close()
            b.close()
    finally:
        srv.terminate()

    print()
    if bad:
        print("  PROBLEMS:")
        for line in bad:
            print("   -", line)
        return 1
    print("  The card is light where the sun is up and dark where it is not,")
    print("  in nine places, and a tap holds until the reader taps again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
