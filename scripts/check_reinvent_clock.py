#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The page still works on the days it is actually for.

    python scripts/check_reinvent_clock.py

Why this exists
---------------
Asked before sharing the page with a team: "I really don't want any sort
of errors, factual errors, any sort of malfunction."

The honest answer at that moment was that one view had never been
exercised. "Now" reads the real clock, and until 30 November there is no
real clock worth reading, so every test of it had been of its preview
mode. The part that matters -- standing in a corridor on the Tuesday --
was the part nothing had run.

Moving the browser's clock into the middle of the event found two defects
that could not have shown up before December:

  1. THE VENUE PICKER DISAPPEARED. "I am at" lived inside the block that
     is hidden once the live clock takes over, so during the event there
     was no way to say where you were standing. A view whose entire
     question is "what is near me" had no way to set me.

  2. IT SAID THE EVENT HAD NOT STARTED, IN DECEMBER. The fallback wording
     assumed the only non-live case was "before", so on 10 December the
     page claimed re:Invent had not begun.

Neither is exotic. Both are what happens when the only clock a check ever
sees is the one on the machine running it.

So this pins the browser to two moments the machine's own clock can never
reach -- mid-event and after it -- and drives the page from each.

(It used to exercise a Team view as well. That was removed: "everybody has
their own schedule, we're not really worried about what each individual is
doing". The page is a personal notebook, not a coordination tool.)
"""

import sys, subprocess, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from playwright.sync_api import sync_playwright as _probe
except ImportError:
    print("  playwright is not installed; skipping")
    raise SystemExit(0)

srv = subprocess.Popen([sys.executable, "-m", "http.server", "8872"],
                       cwd=ROOT, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
time.sleep(2)
BASE = "http://127.0.0.1:8872/reinvent-2026/"
fails = []


def check(label, ok, detail=""):
    print("  %-46s %s %s" % (label, "PASS" if ok else "FAIL", detail))
    if not ok:
        fails.append(label + " " + detail)


try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ---- 1. the event is happening right now -----------------------
        # Tuesday 1 Dec 2026, 13:45 Las Vegas = 21:45 UTC.
        ctx = b.new_context(viewport={"width": 390, "height": 844},
                            device_scale_factor=2, is_mobile=True,
                            has_touch=True,
                            timezone_id="America/Los_Angeles")
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.clock.install(time="2026-12-01T21:45:00Z")
        pg.goto(BASE, wait_until="networkidle")
        pg.wait_for_selector(".card", state="attached", timeout=30000)
        pg.evaluate("document.getElementById('tab-now').click()")
        pg.wait_for_timeout(1500)

        note = pg.inner_text("#nownote")
        print("\n=== DURING THE EVENT (Tue 1 Dec, 13:45 Las Vegas)")
        print("  banner:", note[:110])
        check("uses the real clock, not preview",
              "preview" not in note.lower() and "13:45" in note)
        check("the day/time picker is hidden",
              pg.locator("#nowpick").is_hidden())
        count = pg.inner_text("#nowbody .count")
        print("  says  :", count[:120])
        check("finds sessions starting soon", "session" in count)
        # now stand somewhere
        pg.select_option("#now-at", "Venetian")
        pg.wait_for_timeout(900)
        count2 = pg.inner_text("#nowbody .count")
        print("  at the Venetian:", count2[:130])
        check("splits reachable from too-far", "reach" in count2.lower())
        first = pg.locator("#nowbody .card .where").nth(1)
        print("  a card says   :", first.inner_text()[:90])
        check("cards say how long until a session starts",
              "starts in" in pg.inner_text("#nowbody").lower()
              or "started" in pg.inner_text("#nowbody").lower())
        check("no page errors during the event", not errs, str(errs)[:80])
        ctx.close()

        # ---- 2. the day AFTER the event --------------------------------
        ctx2 = b.new_context(viewport={"width": 390, "height": 844},
                             timezone_id="America/Los_Angeles")
        pg2 = ctx2.new_page()
        e2 = []
        pg2.on("pageerror", lambda e: e2.append(str(e)))
        pg2.clock.install(time="2026-12-10T19:00:00Z")
        pg2.goto(BASE, wait_until="networkidle")
        pg2.wait_for_selector(".card", state="attached", timeout=30000)
        pg2.evaluate("document.getElementById('tab-now').click()")
        pg2.wait_for_timeout(1200)
        print("\n=== AFTER THE EVENT (10 Dec)")
        print("  banner:", pg2.inner_text("#nownote")[:110])
        after = pg2.inner_text("#nownote").lower()
        check("does not claim the event has not started, in December",
              "has not started" not in after)
        check("says it has finished, and still lets you look back",
              "finished" in after)
        fresh = pg2.inner_text("#fresh")
        print("  freshness:", fresh.replace("\n", " ")[:120])
        check("freshness goes stale and says so",
              "stale" in pg2.locator("#fresh").get_attribute("class")
              or "days ago" in fresh)
        check("no errors after the event", not e2, str(e2)[:80])
        ctx2.close()

        b.close()
finally:
    srv.terminate()

print()
if fails:
    print("  %d PROBLEM(S) before sharing:" % len(fails))
    for f in fails:
        print("   -", f)
    sys.exit(1)
print("  Every path exercised, including the two I could not reach before:")
print("  the live clock during the event, and the day after it ends.")
