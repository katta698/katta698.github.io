#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every place a reader might search for must find its dot, under every filter.

    python scripts/check_map_search.py

Why this exists
---------------
Filtering the map to Azure and searching "Mumbai" returned "nothing matches
Mumbai". Azure runs two regions there. It calls them "West India" and "Central
India" -- the city is only ever in our own record, never in the name Azure
publishes -- so the search text held no "Mumbai" and the map said, plainly and
wrongly, that there was nothing there.

The same search worked under AWS, under Google, and under All clouds, because
AWS names the place "Asia Pacific (Mumbai)" and Google names it "Mumbai,
India", and under All clouds the AWS name won the tie. So the fault was
invisible from three of the four ways of looking at it, and the one that failed
failed silently -- a confident sentence saying nothing is there.

Nothing caught it. The health report checks the data behind the map and that
the page renders, but never that a reader typing a city name finds it. A search
box that answers "nothing matches" is worse than no search box: it does not
look broken, it looks like an answer.

So this asks the real page the question a reader would, for every city, every
country and every region code the site carries, under each cloud filter -- and
under a filter, only for regions that filter actually shows.
"""
import io
import json
import os
import socketserver
import sys
import threading
import http.server

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOUDS = ["all", "aws", "azure", "gcp"]


def serve():
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(8891, 8941):
        try:
            srv = socketserver.TCPServer(("127.0.0.1", port), Handler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


# Ask the page the way a reader does: put the text in the box, let the site's
# own handler run, count what it lit. Nothing here reimplements the matching --
# a check that reimplements what it is checking agrees with itself and proves
# nothing.
ASK = """(terms) => {
  const q = document.getElementById('om-q');
  const found = document.getElementById('om-found');
  const out = {};
  terms.forEach(t => {
    q.value = t;
    q.dispatchEvent(new Event('input', { bubbles: true }));
    out[t] = {
      dots: document.querySelectorAll('.om-dot.om-match').length,
      said: (found ? found.textContent : '').trim()
    };
  });
  q.value = '';
  q.dispatchEvent(new Event('input', { bubbles: true }));
  return out;
}"""


def wanted(regions, cloud):
    """What must be findable when this filter is on, and why it is expected.

    Under a cloud filter the map draws only that cloud's regions, so only that
    cloud's places can be found. Asking for Mumbai under a Google-only filter
    when Google had no region there would be the check inventing a fault.
    """
    # Only regions the map can actually draw.
    #
    # Twelve of the 159 have no coordinates -- GovCloud and DoD, whose
    # locations are not published, and regions the vendors have announced but
    # not built. There is no dot to find, so demanding one would be the check
    # inventing a fault. They are not ignored either: unplaceable() below
    # requires the page to say it cannot place them.
    rows = [r for r in regions
            if (cloud == "all" or r.get("cloud") == cloud) and r.get("p")]
    terms = {}
    for r in rows:
        for key in ("city", "country", "code", "name"):
            v = (r.get(key) or "").strip()
            if len(v) < 3:
                continue
            terms.setdefault(v, set()).add("%s/%s" % (r.get("cloud"), r.get("code")))
    return terms


def unplaceable(regions, cloud):
    """Regions this filter carries but cannot draw.

    Searching for one of these must not answer "nothing matches". That is the
    same sentence a genuine miss produces, in the same confident tone, and it
    says the region does not exist when the truth is that its location is not
    published.
    """
    return [r for r in regions
            if (cloud == "all" or r.get("cloud") == cloud) and not r.get("p")]


def main():
    os.chdir(ROOT)
    path = os.path.join(ROOT, "intelligence", "status", "regions.json")
    regions = json.load(io.open(path, encoding="utf-8")).get("regions") or []
    if not regions:
        print("  regions.json holds nothing; cannot check the search.")
        return 1

    from playwright.sync_api import sync_playwright

    srv, port = serve()
    missed, asked = [], 0
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto("http://127.0.0.1:%d/intelligence/status/" % port,
                      wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(2500)

            if not page.query_selector("#om-q"):
                print("  the page has no region search box at all.")
                return 1

            for cloud in CLOUDS:
                page.click('#om-clouds .pm-cl[data-cl="%s"]' % cloud)
                page.wait_for_timeout(700)
                terms = wanted(regions, cloud)
                got = page.evaluate(ASK, sorted(terms))
                asked += len(terms)
                blind = [t for t, r in got.items() if not r["dots"]]
                for t in sorted(blind):
                    missed.append((cloud, t, sorted(terms[t])[:2]))

                # And the ones that cannot be drawn must be admitted, not
                # denied.
                gone = [r.get("code") for r in unplaceable(regions, cloud)
                        if r.get("code")]
                said = page.evaluate(ASK, sorted(gone)) if gone else {}
                asked += len(gone)
                denied = [c for c in gone
                          if "not on the map" not in (said.get(c) or {}).get("said", "")]
                for c in sorted(denied):
                    missed.append((cloud, c,
                                   ["carried but unplaceable — the page denies it"]))

                print("  %-6s %4d term(s) asked, %d found nothing; "
                      "%d unplaceable, %d denied"
                      % (cloud, len(terms), len(blind), len(gone), len(denied)))
            browser.close()
    finally:
        srv.shutdown()

    print()
    if missed:
        print("  %d SEARCH(ES) THAT SHOULD HAVE FOUND A DOT AND DID NOT\n"
              % len(missed))
        for cloud, term, who in missed[:30]:
            print("  - with %-5s selected, \"%s\" finds nothing — but %s is there"
                  % (cloud, term, ", ".join(who)))
        if len(missed) > 30:
            print("    ...and %d more" % (len(missed) - 30))
        print("\n  A search that answers \"nothing matches\" does not look")
        print("  broken. It looks like an answer.")
        return 1

    print("  every city, country, region name and region code finds its dot,")
    print("  and every region that cannot be drawn says so — %s asked across"
          % "{:,}".format(asked))
    print("  %d filters." % len(CLOUDS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
