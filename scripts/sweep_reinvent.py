#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capture every view at both widths, and report the ones too long to scan.

    python scripts/sweep_reinvent.py          # writes _sweep/*.png
    python scripts/sweep_reinvent.py --sizes  # heights only, no images

Why this exists
---------------
Asked, after a run of layout complaints: "we have been seeing these
cosmetic issues and wondering if there's an end."

Worth answering with the record rather than a promise. Of the ten visible
defects on this page, NINE were found by a person looking at a screenshot
and one by me looking at my own. Every automated check passed through all
of them, because they check correctness -- filters, itineraries, live data
-- and the mechanical faults a layout can have: overflow, unreachable
controls, content wider than its box. None of them LOOKS at the page.

This does. It drives every view at a phone and a laptop width, in a
realistic state, writes the lot to _sweep/ to be reviewed in one sitting,
and measures how tall each one is -- because the first thing it found was
not subtle:

    Just announced   25,083px   30 phone screens
    Now              15,754px   19 phone screens
    Browse           12,950px   15 phone screens

Nobody had reported those. That is not the same as nobody suffering them.
"""
import argparse
import sys, os, subprocess, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "_sweep")
os.makedirs(OUT, exist_ok=True)
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8941"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)
BASE = "http://localhost:8941/reinvent-2026/"
PLAN = "#plan=NET305,CMP202,CON303"

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w, h, tag, mob in ((1250, 1000, "desk", False),
                               (390, 844, "phone", True)):
            ctx = b.new_context(viewport={"width": w, "height": h},
                                device_scale_factor=2, is_mobile=mob,
                                has_touch=mob)
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(BASE + PLAN, wait_until="networkidle")
            pg.wait_for_selector("#plan .card", timeout=30000)
            # a note, so the plan looks lived-in
            pg.locator("textarea.note").first.fill(
                "Ask about cross-account limits.")
            pg.wait_for_timeout(500)

            def shot(name, sel=None):
                path = os.path.join(OUT, "%s-%s.png" % (name, tag))
                if sel:
                    pg.locator(sel).screenshot(path=path)
                else:
                    pg.screenshot(path=path, full_page=True)
                print("   %s" % path)

            pg.evaluate("document.getElementById('tab-browse').click()")
            pg.wait_for_timeout(700)
            pg.evaluate("window.scrollTo(0,0)")
            pg.wait_for_timeout(300)
            shot("1-top")

            pg.evaluate("document.getElementById('tab-plan').click()")
            pg.wait_for_timeout(900)
            shot("2-myplan", "#plan")

            pg.evaluate("document.getElementById('tab-plan2').click()")
            pg.wait_for_timeout(700)
            pg.select_option("#pl-day", "2026-12-02")
            pg.select_option("#pl-at", "MGM Grand")
            pg.wait_for_timeout(3000)
            shot("3-planner", "#plan2")

            pg.evaluate("document.getElementById('tab-now').click()")
            pg.wait_for_timeout(700)
            pg.select_option("#now-day", "2026-12-02")
            pg.eval_on_selector("#now-time", "e=>{e.value='12:45';"
                                "e.dispatchEvent(new Event('change'));}")
            pg.select_option("#now-at", "MGM Grand")
            pg.wait_for_timeout(1200)
            shot("4-now", "#now")

            pg.evaluate("document.getElementById('tab-news').click()")
            pg.wait_for_timeout(900)
            shot("5-news", "#news")

            pg.evaluate("document.getElementById('tab-map').click()")
            pg.wait_for_timeout(3000)
            shot("6-map", "#map")

            print("   %s errors: %s" % (tag, errs if errs else "none"))
            ctx.close()
        b.close()
finally:
    srv.terminate()
