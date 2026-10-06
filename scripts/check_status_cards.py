#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A cloud card opens its own incidents, and opens exactly one thing.

    python scripts/check_status_cards.py
    python scripts/check_status_cards.py --live

Why this exists
---------------
Asked for as: "can these be clickable instead of having incidents show in same
page?" The three summary cards were plain divs and every incident was printed
underneath them, so the page answered "is anything broken" in one screen and
then spent several more on detail nobody had asked for yet.

Three things have to hold, and two of them failed once already:

  ONE DIALOG.  The card's attribute was first called data-inc. The 90-day
  timeline already puts data-inc on every day cell -- a comma-separated list of
  incident indexes -- and pm.js has a document-level handler for it. So one tap
  opened two dialogs, the timeline's landing on top reading "Nothing began on
  this day", because "aws".split(',').map(Number) is [NaN] and matches nothing.
  Both handlers were correct; the attribute name was the bug. The first version
  of this check asserted the panel was visible and passed while a second dialog
  covered it, which is why the assertion is now "exactly one".

  ONLY WHEN THERE IS SOMETHING TO OPEN.  A healthy card stays a div. If all
  three were tappable, a reader would tap "No active incidents", get an empty
  panel, and stop trusting that any of them do anything.

  REACHABLE WITHOUT SCRIPTS.  The incidents stay in the HTML; they are hidden
  only under html.ck-js, the class the page sets in its own head when scripts
  run. With JavaScript off nothing is hidden and the card's href jumps to them,
  which is the page as it behaved before. Checked here because it is invisible
  in normal use -- it would rot silently.
"""
import argparse
import http.server
import os
import re
import json
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = "/intelligence/status/"


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
    for port in range(8701, 8751):
        try:
            srv = _Threaded(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


OPEN_DIALOGS = "() => document.querySelectorAll('dialog[open]').length"


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
            for engine, label in (("chromium", "Chrome / Edge"),
                                  ("webkit", "Safari, iPad, iPhone")):
                b = getattr(pw, engine).launch()
                ctx = b.new_context(**pw.devices["iPhone 13"])
                pg = ctx.new_page()
                pg.goto(base + PATH, wait_until="domcontentloaded", timeout=60000)
                pg.wait_for_timeout(1800)

                taps = pg.locator(".scard.tap")
                n_tap = taps.count()
                n_src = pg.locator(".inc-src").count()

                # Only cards with incidents are tappable, and every tappable
                # card has a section to open.
                if n_tap != n_src:
                    problems.append(
                        "%s: %d tappable card(s) but %d incident section(s) -- "
                        "a card that opens nothing, or incidents with no way in"
                        % (label, n_tap, n_src))

                if n_src and pg.locator(".inc-src").first.is_visible():
                    problems.append(
                        "%s: the incidents are still printed on the page; the "
                        "card was meant to replace that, not add to it" % label)

                opened = 0
                if n_tap:
                    taps.first.click()
                    pg.wait_for_timeout(600)
                    opened = pg.evaluate(OPEN_DIALOGS)
                    if opened != 1:
                        problems.append(
                            "%s: tapping a card opened %d dialog(s), not 1 -- "
                            "two handlers are claiming the same click"
                            % (label, opened))
                    if not pg.locator("#inc-dialog").is_visible():
                        problems.append(
                            "%s: the panel that opened is not the incident "
                            "panel" % label)
                    n_in = pg.locator("#inc-dialog .inc").count()
                    if n_in < 1:
                        problems.append(
                            "%s: the panel opened empty" % label)
                    pg.keyboard.press("Escape")
                    pg.wait_for_timeout(400)
                    if pg.evaluate(OPEN_DIALOGS) != 0:
                        problems.append(
                            "%s: Escape did not close the panel" % label)
                    print("    %-22s %d tappable, panel held %d incident(s), "
                          "%d dialog open" % (label, n_tap, n_in, opened))
                else:
                    print("    %-22s every cloud healthy, no card tappable"
                          % label)
                ctx.close()

                # Scripts off: the page must still carry its own detail.
                ctx = b.new_context(java_script_enabled=False,
                                    **pw.devices["iPhone 13"])
                pg = ctx.new_page()
                pg.goto(base + PATH, wait_until="domcontentloaded", timeout=60000)
                pg.wait_for_timeout(600)
                if pg.locator(".inc-src").count():
                    if not pg.locator(".inc-src").first.is_visible():
                        problems.append(
                            "%s with scripts off: the incidents are hidden and "
                            "nothing can reveal them" % label)
                    href = pg.locator(".scard.tap").first.get_attribute("href")
                    if not (href or "").startswith("#inc-"):
                        problems.append(
                            "%s with scripts off: the card does not link to "
                            "the incidents (href %r)" % (label, href))

                ctx.close()
                b.close()

        # --- the map must not call a resolved incident open ------------------
        #
        # Reported: a region panel headed "Open right now" whose first line
        # began "[RESOLVED]". status.json's clouds[] carries open and closed
        # incidents alike; the cards filter it with is_open() and the map took
        # the list whole.
        #
        # Its own desktop context, because the dots are not reachable at phone
        # size -- run inside the iPhone loop this reported "no dot to click"
        # on both engines and passed without testing anything.
        #
        # The store is replaced rather than waited for, so it fires on every
        # run instead of only during an outage.
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch()
                # service_workers="block" is load-bearing, not hygiene.
                # page.route() does NOT intercept a request made BY a service
                # worker, and this site registers one. The widget fetches
                # status.json twice -- once on DOMContentLoaded and again 400ms
                # after load -- so with the worker active the second fetch went
                # around the mock and returned the REAL file. The assertion
                # then compared live data against a synthetic expectation and
                # failed on correct code. Blocking the worker is what makes
                # the payload below the one actually under test.
                ctx = b.new_context(viewport={"width": 1280, "height": 1000},
                                    service_workers="block")
                pg = ctx.new_page()
                pg.route("**/intelligence/status.json", lambda route: route.fulfill(
                    status=200, content_type="application/json",
                    body=json.dumps({
                        "checked": "2026-01-01T00:00:00Z",
                        "clouds": {"aws": [{
                            "title": "[RESOLVED] Synthetic packet loss",
                            "service": "Internet Connectivity",
                            "region": "Spain", "region_code": "eu-south-2",
                            "url": "", "update": "closed before this ran",
                        }], "azure": [], "gcp": []},
                        "sources": {}, "history_count": 0,
                    })))
                pg.goto(base + PATH, wait_until="domcontentloaded", timeout=60000)
                pg.wait_for_timeout(6000)
                clicked = pg.evaluate(
                    """() => {
                       const all = [...document.querySelectorAll(
                         'svg [data-code], svg [data-r], svg circle, svg g')];
                       const hit = all.find(e => /eu-south-2|Spain/i.test(
                         (e.getAttribute('data-code') || '') + ' ' +
                         (e.getAttribute('data-r') || '') + ' ' +
                         (e.getAttribute('aria-label') || '')));
                       if (!hit) { return false; }
                       hit.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                       return true; }""")
                if not clicked:
                    problems.append(
                        "the map check could not find a Spain dot to open, so it "
                        "tested nothing -- a check that cannot reach its subject "
                        "passes for the wrong reason")
                else:
                    pg.wait_for_timeout(800)
                    body = pg.evaluate("() => document.body.innerText")
                    m = re.search(r"Open right now([\s\S]{0,400})", body)
                    bad = bool(m and "[RESOLVED]" in m.group(1))
                    if bad:
                        problems.append(
                            "the map lists a resolved incident under \"Open right "
                            "now\" -- the heading is the strongest claim on the "
                            "page and the title beneath it says the opposite")
                    print("  map panel: a resolved incident is %s"
                          % ("STILL SHOWN as open" if bad else "kept out of it"))
                ctx.close()
                b.close()
        except Exception as exc:                                # noqa: BLE001
            problems.append("the map check could not run: %s" % str(exc)[:90])

        # --- the nav light must count what the page counts -------------------
        #
        # Asked as: "in the blog page in the cloud status, why AWS still shows
        # three incidents when the live status page just shows two? So are
        # these two not in sync?" They were not. The light in the bar summed
        # clouds[*].length, which counts a "[RESOLVED]" entry the page filters
        # out, so it read 3 open while the page it links to listed 2.
        #
        # This is the SECOND place that bug has been fixed -- the map had it
        # too -- so the rule now has a test rather than only a comment asking
        # two files to agree. The payload carries one resolved and one open
        # incident, and the only correct answer is 1.
        #
        # Measured on /blog/ rather than the status page: the widget
        # deliberately skips the page you are already on, so asserting it
        # there would test nothing.
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch()
                # service_workers="block" is load-bearing, not hygiene.
                # page.route() does NOT intercept a request made BY a service
                # worker, and this site registers one. The widget fetches
                # status.json twice -- once on DOMContentLoaded and again 400ms
                # after load -- so with the worker active the second fetch went
                # around the mock and returned the REAL file. The assertion
                # then compared live data against a synthetic expectation and
                # failed on correct code. Blocking the worker is what makes
                # the payload below the one actually under test.
                ctx = b.new_context(viewport={"width": 1280, "height": 1000},
                                    service_workers="block")
                pg = ctx.new_page()
                pg.route("**/intelligence/status.json", lambda route: route.fulfill(
                    status=200, content_type="application/json",
                    body=json.dumps({
                        "checked": "2026-01-01T00:00:00Z",
                        "clouds": {"aws": [
                            {"title": "[RESOLVED] Synthetic packet loss",
                             "service": "Internet Connectivity",
                             "region": "Spain", "region_code": "eu-south-2",
                             "url": "", "update": "closed before this ran"},
                            {"title": "Synthetic region availability",
                             "service": "EC2",
                             "region": "Ohio", "region_code": "us-east-2",
                             "url": "", "update": "genuinely open"},
                        ], "azure": [], "gcp": []},
                        # The card reports "unknown" for a cloud whose source
                        # did not fetch, which is correct and is not what this
                        # is testing -- so the sources have to say ok here or
                        # the assertion never reaches the count.
                        "sources": {"aws": {"ok": True}, "azure": {"ok": True},
                                    "gcp": {"ok": True}},
                        "history_count": 0,
                    })))
                pg.goto(base + "/blog/", wait_until="domcontentloaded",
                        timeout=60000)
                pg.wait_for_timeout(3000)
                said = pg.evaluate(
                    """() => {
                       const a = document.querySelector(
                         'a[href="/intelligence/status/"].is-live');
                       return a ? (a.getAttribute('title') || '') : null; }""")
                if said is None:
                    problems.append(
                        "the nav status light never lit with an open incident "
                        "in the feed, so its count was not tested -- a check "
                        "that cannot reach its subject passes for the wrong "
                        "reason")
                elif "1 open incident" not in said:
                    problems.append(
                        "the nav status light says %r while the page it links "
                        "to lists 1 open -- the light counted a resolved "
                        "incident, so the bar and the page disagree" % said)
                else:
                    print("  nav light: counts 1 open, not the resolved one")

                # The sidebar Cloud status card, same payload. It is rendered
                # at BUILD time by sync_blog.py and refreshed from this fetch,
                # so both halves have to agree with the page: the card must
                # read "1 incident", never 2. Reported as "three incidents
                # still shows in the blog page" when the status page said two.
                card = pg.evaluate(
                    """() => {
                       const c = document.querySelector('.cloud-status-card');
                       if (!c) { return null; }
                       const row = [...c.querySelectorAll('.cs-row')].find(
                         r => (r.querySelector('.cs-n') || {}).textContent
                              === 'AWS');
                       if (!row) { return null; }
                       return (row.querySelector('.cs-v') || {}).textContent
                              || ''; }""")
                if card is None:
                    problems.append(
                        "the blog sidebar has no Cloud status card with an AWS "
                        "row, so its count was not tested -- a check that "
                        "cannot reach its subject passes for the wrong reason")
                elif card.strip() != "1 incident":
                    problems.append(
                        "the Cloud status card says %r while the page it links "
                        "to lists 1 open -- the card counted a resolved "
                        "incident, or never refreshed off the build-time "
                        "snapshot" % card.strip())
                else:
                    print("  status card: reads 1 incident, live off the feed")
                ctx.close()
                b.close()
        except Exception as exc:                                # noqa: BLE001
            problems.append("the nav light check could not run: %s"
                            % str(exc)[:90])
    finally:
        if srv:
            srv.shutdown()


    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for p in problems[:12]:
            print("  - %s" % p)
        return 1
    print("  Cards open their own incidents, one panel at a time, and the")
    print("  detail is still there with scripts off.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
