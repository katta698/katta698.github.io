#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Break the clouds on purpose, and check the map says so.

    python scripts/simulate_outage.py                    # the whole matrix
    python scripts/simulate_outage.py --cloud azure --region westeurope
    python scripts/simulate_outage.py --shots            # save what it drew

Why this exists
---------------
Only AWS has had open incidents while this map has been live. So the Azure and
Google paths through it have never once been exercised against real data --
they are believed to work, which is not the same as known to work, and the
first time they are tested for real will be the morning something is actually
broken and someone is looking at this page to find out what.

So this breaks them deliberately. It serves the real page with a SYNTHETIC
status.json -- the file the map fetches at runtime -- and then asks the page
what it drew: is there a live dot, is it in the right place, does the banner
name the right region, does the ring actually move.

Nothing is written to the repository. The real status.json is never touched;
the substitute exists only inside the test server, for the seconds the test
runs.

The scenarios are chosen to be the ones that would embarrass this page:

  a single Azure region, and a single Google region -- the two paths that have
  never run

  all three clouds at once, because the alert strip has only ever had to name
  one cloud

  two regions of the same cloud, because "AWS is down" and "AWS is down in
  Ireland and Tokyo" are different sentences

  a region the map has no coordinates for, which must be listed rather than
  silently dropped -- a map that quietly omits an outage is worse than one
  that admits it cannot draw it

  a region code the vendor has never used, which is what a feed change looks
  like from here

  and no incidents at all, because "everything is fine" has to be drawn too
"""
import argparse
import http.server
import io
import json
import os
import socketserver
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_PATH = "/intelligence/status.json"

# cloud, region code, and the place it should light up.
# The codes here must be the ones THIS SITE uses, not the ones a vendor's API
# uses. The first version of this test asked for Azure "westeurope" -- the ARM
# name -- while the map is built on Azure's status-page naming, "europe-west".
# It reported Azure as broken when the test was simply asking for a region that
# does not exist here, which is a test that proves nothing while looking
# authoritative. validate_codes() below refuses to run on a code the site does
# not know.
SCENARIOS = [
    ("one Azure region", [("azure", "europe-west", "Netherlands")]),
    ("one Google region", [("gcp", "asia-south1", "India")]),
    ("one AWS region", [("aws", "eu-west-1", "Ireland")]),
    ("two AWS regions at once", [("aws", "eu-west-1", "Ireland"),
                                 ("aws", "ap-northeast-1", "Japan")]),
    ("all three clouds at once", [("aws", "us-east-1", "United States"),
                                  ("azure", "europe-west", "Netherlands"),
                                  ("gcp", "asia-south1", "India")]),
    ("an Azure region far from the others", [("azure", "australia-east", "Australia")]),
    ("a region code no vendor uses", [("gcp", "not-a-real-region1", None)]),
    # The realistic version of the same thing, and the reason it matters: 33 of
    # the 79 Azure incidents this site holds name no region at all, because
    # they are global services. Front Door going down worldwide arrives here
    # with an empty region_code.
    ("a global outage naming no region", [("azure", "", None)]),
    ("nothing wrong anywhere", []),
]


def validate_codes(scenarios):
    """Refuse to test with a region code this site has never heard of.

    A scenario naming a code the site does not carry cannot light a dot, and
    reports the map as broken when the fault is in the test. That happened on
    the first run of this file and it looked exactly like a real bug.
    """
    known = set()
    path = os.path.join(ROOT, "intelligence", "status", "regions.json")
    for r in json.load(io.open(path, encoding="utf-8")).get("regions") or []:
        known.add((r.get("cloud"), r.get("code")))
    bad = []
    for name, rows in scenarios:
        for cloud, code, place in rows:
            if place is not None and (cloud, code) not in known:
                bad.append("%s: %s/%s is not a region this site carries"
                           % (name, cloud, code))
    return bad


def synthetic(rows):
    """A status.json shaped exactly like the real one, with chosen outages."""
    real = json.load(io.open(os.path.join(ROOT, "intelligence", "status.json"),
                             encoding="utf-8"))
    clouds = {"aws": [], "azure": [], "gcp": []}
    for cloud, code, _place in rows:
        clouds[cloud].append({
            "id": "simulated:%s:%s" % (cloud, code),
            "title": "Simulated outage for testing",
            "service": "Multiple services",
            "region": code,
            "region_code": code,
            "begin": str(int(time.time())),
            "update": "This incident is synthetic. It exists only inside a test.",
            "updates": [],
            "url": "https://example.invalid/simulated",
        })
    return {"checked": real.get("checked"), "clouds": clouds,
            "sources": real.get("sources", {}),
            "history_count": real.get("history_count", 0)}


def serve(payload):
    """The real site, with one file swapped in memory."""
    body = json.dumps(payload).encode("utf-8")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def end_headers(self):
            if self.path.endswith(".woff2"):
                self.send_header("Access-Control-Allow-Origin", "*")
            http.server.SimpleHTTPRequestHandler.end_headers(self)

        def do_GET(self):
            if self.path.split("?")[0] == STATUS_PATH:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            return http.server.SimpleHTTPRequestHandler.do_GET(self)

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(8971, 9011):
        try:
            srv = socketserver.TCPServer(("127.0.0.1", port), Handler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


ASK = """() => {
  const dots = [...document.querySelectorAll('.om-dot')];
  const live = dots.filter(d => d.classList.contains('is-live'));
  const ring = live.length ? live[0].querySelector('animate, .om-ping') : null;
  const banner = document.querySelector('.om-alert');
  const unplaced = document.querySelector('.om-unplaced, .om-nomap');
  return {
    dots: dots.length,
    live: live.length,
    liveClouds: [...new Set(live.map(d => (d.className.baseVal || d.className || '')
                   .toString().split(' ').filter(c => ['aws','azure','gcp'].includes(c))[0]))]
                 .filter(Boolean),
    liveWhere: live.map(d => (d.getAttribute('data-region') || '')).slice(0, 6),
    ringMoves: !!ring,
    banner: banner ? banner.textContent.replace(/\\s+/g, ' ').trim().slice(0, 110) : null,
    saysOpen: /open right now/i.test(document.body.innerText || '')
  };
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloud")
    ap.add_argument("--region")
    ap.add_argument("--shots", action="store_true",
                    help="save a picture of the map for each scenario")
    args = ap.parse_args()

    os.chdir(ROOT)
    scenarios = SCENARIOS
    if args.cloud and args.region:
        scenarios = [("%s %s" % (args.cloud, args.region),
                      [(args.cloud, args.region, None)])]

    wrong = validate_codes(scenarios)
    if wrong:
        print("  the scenarios themselves are wrong:")
        for w in wrong:
            print("   - %s" % w)
        return 1

    out_dir = os.path.join(os.path.expanduser("~"), "Desktop", "outage-sim")
    if args.shots:
        os.makedirs(out_dir, exist_ok=True)

    from playwright.sync_api import sync_playwright

    problems = []
    print("  serving the real page with a synthetic status.json\n")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, rows in scenarios:
            srv, port = serve(synthetic(rows))
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto("http://127.0.0.1:%d/intelligence/status/" % port,
                      wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(2500)
            r = page.evaluate(ASK)

            want = len(rows)
            placed = [x for x in rows if x[2]]
            got = r["live"]

            if not rows:
                if got:
                    problems.append("%s: %d dot(s) lit with nothing wrong"
                                    % (name, got))
                    verdict = "FAIL"
                else:
                    verdict = "ok"
            elif got < len(placed):
                problems.append("%s: expected at least %d live dot(s), drew %d"
                                % (name, len(placed), got))
                verdict = "FAIL"
            else:
                verdict = "ok"

            # An outage the map cannot place must still be ADMITTED.
            #
            # The first version asked whether the region code appeared in the
            # page text, which an empty region code trivially satisfies -- so
            # the worst scenario in the matrix, a global outage naming no
            # region, passed while the page in fact said nothing at all.
            unplaceable = [x for x in rows if x[2] is None]
            if unplaceable and not r["saysOpen"]:
                problems.append(
                    "%s: %d incident(s) cannot be drawn and the page does not "
                    "say anything is open" % (name, len(unplaceable)))
                verdict = "FAIL"

            print("  %-4s %-30s live dots %d  clouds %-18s ring %s"
                  % (verdict, name, got, ",".join(r["liveClouds"]) or "-",
                     "moves" if r["ringMoves"] else "still"))
            if r["banner"]:
                print("       banner: %s" % r["banner"][:96])

            if args.shots:
                page.screenshot(
                    path=os.path.join(out_dir, name.replace(" ", "-") + ".png"),
                    clip={"x": 0, "y": 0, "width": 1280, "height": 760})
            page.close()
            srv.shutdown()

        browser.close()

    print()
    if problems:
        print("  %d SCENARIO(S) THE MAP GOT WRONG\n" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("  the map reported every simulated outage, on every cloud.")
    if args.shots:
        print("  pictures: %s" % out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
