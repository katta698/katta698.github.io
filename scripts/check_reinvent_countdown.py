#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The countdown is right on every side of the event, on both pages.

Asked for: "these many days to go for the event ... some sort of creative
way showing 60 days to go", and the same thing on the contact card.

A countdown is the one number on a page that a reader checks against
their own calendar, and it has four states rather than one -- far off,
the last fortnight, during, and over. Three of those cannot be seen on
the day the code is written, which is exactly how a page ends up still
saying "2 days to go" in January. So the clock is pinned to five moments
and the page is asked what it says at each.

Both surfaces are checked together, because they are two implementations
of one fact: the planner computes it from the event dates in its config,
and the contact card carries fifteen lines of its own so it does not have
to load the planner's app. Two implementations agree today and drift in
March; the last assertion is that on the same pinned day they print the
same number.
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

PORT = 8975
PLANNER = "http://127.0.0.1:%d/reinvent-2026/" % PORT
CARD = "http://127.0.0.1:%d/connect/" % PORT

# moment, label, expected number, expected words in the unit line
MOMENTS = [
    ("2026-09-23T18:00:00Z", "two months out", "68", "days to go"),
    ("2026-11-20T18:00:00Z", "ten days out", "10", "days to go"),
    ("2026-11-29T18:00:00Z", "the day before", "1", "day to go"),
    ("2026-12-02T21:00:00Z", "mid-event", "3", "happening now"),
    ("2026-12-06T18:00:00Z", "after it ends", None, "wrap"),
]

READ_PLANNER = """()=>{
  const g = s => { const e = document.querySelector(s);
    return e ? e.textContent.trim() : null; };
  const dot = document.querySelector('#cd-unit .cd-live');
  return { hidden: document.getElementById('countdown').hidden,
           num: g('#cd-num'), unit: g('#cd-unit'), note: g('#cd-note'),
           marks: document.querySelectorAll('#cd-marks i').length,
           dot: !!dot,
           beat: getComputedStyle(document.querySelector('#cd-num'))
                   .animationName };
}"""

READ_CARD = """()=>{
  const b = document.getElementById('rein');
  const g = id => { const e = document.getElementById(id);
    return e ? e.textContent.trim() : null; };
  return { hidden: !b || b.hidden, num: g('rein-n'), title: g('rein-t'),
           sub: g('rein-s'), href: b ? b.getAttribute('href') : null };
}"""


def main():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                           cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    time.sleep(2)
    bad = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            for when, label, want_num, want_words in MOMENTS:
                ctx = b.new_context(viewport={"width": 1250, "height": 1000},
                                    timezone_id="America/Los_Angeles")
                errs = []
                pg = ctx.new_page()
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.clock.install(time=when)
                pg.goto(PLANNER, wait_until="domcontentloaded")
                pg.wait_for_selector("#browse .card", timeout=30000)
                pg.wait_for_timeout(700)
                got = pg.evaluate(READ_PLANNER)

                card = ctx.new_page()
                card.clock.install(time=when)
                card.goto(CARD, wait_until="domcontentloaded")
                card.wait_for_timeout(700)
                cgot = card.evaluate(READ_CARD)

                print("  %-15s planner %-4s %-24s marks %-3s | card %-4s %s"
                      % (label, got["num"], got["unit"], got["marks"],
                         cgot["num"], (cgot["title"] or "")[:26]))

                if got["hidden"]:
                    bad.append("%s: the planner shows no countdown at all"
                               % label)
                if want_num and got["num"] != want_num:
                    bad.append("%s: the planner says %r, not %r"
                               % (label, got["num"], want_num))
                if want_words not in (got["unit"] or "").lower():
                    bad.append("%s: the planner's countdown reads %r, which "
                               "does not say %r"
                               % (label, got["unit"], want_words))
                if cgot["hidden"]:
                    bad.append("%s: the contact card shows no countdown"
                               % label)
                elif cgot["href"] != "/reinvent-2026/":
                    bad.append("%s: the card's countdown does not link to the "
                               "planner (%r)" % (label, cgot["href"]))
                # The agreement that matters: two implementations, one fact.
                if not got["hidden"] and not cgot["hidden"]:
                    if (got["num"] or "").strip() != (cgot["num"] or "").strip():
                        bad.append("%s: the planner says %r and the contact "
                                   "card says %r on the same day"
                                   % (label, got["num"], cgot["num"]))
                # The number is meant to be alive, and the thing that
                # makes it look alive must survive the minute tick: the
                # pulsing dot lives inside the line the tick rewrites, so
                # a textContent assignment there would delete it a minute
                # after load, on a page nobody watches for a minute.
                if got["beat"] in (None, "none", ""):
                    bad.append("%s: the countdown number is not pulsing "
                               "(animation-name %r)" % (label, got["beat"]))
                if not got["dot"]:
                    bad.append("%s: the live dot is missing" % label)
                pg.clock.fast_forward("02:00")
                pg.wait_for_timeout(400)
                after = pg.evaluate(READ_PLANNER)
                if not after["dot"]:
                    bad.append("%s: the live dot is gone a minute later -- "
                               "the tick rewrote the line it lives in"
                               % label)
                if after["num"] != got["num"]:
                    bad.append("%s: the number changed on the tick, %r to %r"
                               % (label, got["num"], after["num"]))
                if errs:
                    bad.append("%s: %s" % (label, errs[0][:90]))
                ctx.close()
            b.close()
    finally:
        srv.terminate()

    print()
    if bad:
        print("  PROBLEMS:")
        for line in bad:
            print("   -", line)
        print()
        print("  A countdown is checked against the reader's own calendar.")
        print("  Being wrong by one is being wrong.")
        return 1
    print("  The countdown is right two months out, ten days out, the day")
    print("  before, mid-event and after it ends -- and the card agrees with")
    print("  the planner on every one of them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
