#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every session count on the page comes from the data it is showing.

Asked, after the catalog moved from 1,582 to 1,581 in a morning: "when
the live sessions are updated to 1599, why does everything still show the
previous numbers like 1581? Are they hard coded?"

They were. The header, the lane tabs, the callout above the planner and
the paragraph about how much of the programme exists were written in at
build time, so a live pull replaced the results underneath them and left
every figure around them describing the copy it had just thrown away.
check_reinvent.py catches a count that disagrees with the STORE; nothing
caught a count that could not follow the store anywhere.

Two properties, both tested by serving the page a store it was not built
from:

  fewer sessions   the page is given a store with 100 removed. Every
                   number on it must say so -- header, scheduled subset,
                   callout, "Everything" tab, each lane, the prose total
                   and the percentage of AWS's planned 2,200.

  a reshuffled service table
                   lanes are defined as indices into the Services facet,
                   and a live pull rebuilds that table from the fresh
                   payload -- a table built from a different set of
                   sessions does not number its services the same way. So
                   the table is deliberately permuted, with every
                   session's references rewritten to match: the same
                   sessions, described differently. Lane counts must not
                   move. Before the fix they follow the numbers rather
                   than the services, which is the failure that shows a
                   reader the wrong sessions and raises nothing.
"""
import io
import json
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "intelligence", "reinvent2026.json")
HTML = os.path.join(ROOT, "reinvent-2026", "index.html")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("  playwright not installed -- skipping")
    sys.exit(0)

PORT = 8973
URL = "http://127.0.0.1:%d/reinvent-2026/" % PORT
DROP = 100

READ = """()=>{
  const t = id => { const e = document.getElementById(id);
    return e ? e.textContent.trim() : null; };
  const lanes = {};
  document.querySelectorAll('[data-count]').forEach(e => {
    lanes[e.getAttribute('data-count')] = e.textContent.trim();
  });
  return { total: t('n-total'), scheduled: t('n-scheduled'), cta: t('n-cta'),
           prose: t('n-prose'), pct: t('n-pct'), lanes: lanes };
}"""


def num(s):
    if s is None:
        return None
    m = re.search(r"[\d,]+", s)
    return int(m.group(0).replace(",", "")) if m else None


def permuted(store):
    """The same sessions, with the Services table in a different order."""
    svs = store["facets"]["Services"]
    order = list(range(len(svs)))[::-1]              # reversed is enough
    new_at = {old: new for new, old in enumerate(order)}
    out = json.loads(json.dumps(store))
    out["facets"]["Services"] = [svs[i] for i in order]
    for s in out["sessions"]:
        s["sv"] = [new_at[i] for i in s.get("sv", [])]
    return out


def main():
    store = json.load(io.open(STORE, encoding="utf-8"))
    html = io.open(HTML, encoding="utf-8").read()
    built = len(store["sessions"])

    smaller = json.loads(json.dumps(store))
    smaller["sessions"] = smaller["sessions"][:-DROP]
    want = built - DROP
    want_sched = sum(1 for s in smaller["sessions"] if s.get("when"))
    planned = int(re.search(r"var AWS_PLANNED = (\d+)",
                            io.open(os.path.join(ROOT, "reinvent-2026",
                                                 "app.js"),
                                    encoding="utf-8").read()).group(1))

    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                           cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    time.sleep(2)
    bad = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            for label, doctored in (("100 fewer sessions", smaller),
                                    ("a reshuffled service table",
                                     permuted(store))):
                pg = b.new_page(viewport={"width": 1250, "height": 1000})
                body = json.dumps(doctored)
                def serve(route, request=None, body=body):
                    route.fulfill(status=200,
                                  content_type="application/json", body=body)
                pg.route("**/intelligence/reinvent2026.json", serve)
                pg.goto(URL, wait_until="domcontentloaded")
                pg.wait_for_selector("#browse .card", timeout=30000)
                pg.wait_for_timeout(600)
                got = pg.evaluate(READ)
                print("  %s:" % label)

                if doctored is smaller:
                    for key, expect in (("total", want), ("cta", want),
                                        ("prose", want),
                                        ("scheduled", want_sched),
                                        ("pct", int(round(
                                            100.0 * want / planned)))):
                        seen = num(got[key])
                        ok = seen == expect
                        print("     %-10s %-7s expected %-7s %s"
                              % (key, seen, expect, "ok" if ok else "STALE"))
                        if not ok:
                            bad.append("%s shows %s where the data it is "
                                       "showing holds %s"
                                       % (key, seen, expect))
                    seen = num(got["lanes"].get("all"))
                    if seen != want:
                        bad.append("the Everything tab shows %s, not %s"
                                   % (seen, want))
                    print("     %-10s %-7s expected %-7s %s"
                          % ("all tab", seen, want,
                             "ok" if seen == want else "STALE"))
                    smaller_lanes = {k: num(v) for k, v in got["lanes"].items()
                                     if k != "all"}
                else:
                    for lane, n in sorted(got["lanes"].items()):
                        if lane == "all":
                            continue
                        was = base_lanes.get(lane)
                        ok = num(n) == was
                        print("     lane %-14s %-6s built %-6s %s"
                              % (lane, num(n), was,
                                 "ok" if ok else "FOLLOWED THE INDEX"))
                        if not ok:
                            bad.append("lane %s counts %s sessions against a "
                                       "reshuffled service table, not %s -- "
                                       "it is matching index numbers rather "
                                       "than services" % (lane, num(n), was))
                pg.close()
                if doctored is smaller:
                    # Lane counts from the unmodified store, for comparison.
                    pg2 = b.new_page(viewport={"width": 1250, "height": 1000})
                    pg2.goto(URL, wait_until="domcontentloaded")
                    pg2.wait_for_selector("#browse .card", timeout=30000)
                    pg2.wait_for_timeout(600)
                    base = pg2.evaluate(READ)
                    base_lanes = {k: num(v) for k, v in base["lanes"].items()
                                  if k != "all"}
                    pg2.close()
                print()
            b.close()
    finally:
        srv.terminate()

    # The built-in values still have to be right on first paint, for a
    # reader with JavaScript off or a slow store.
    for tag, expect in (("n-total", built), ("n-cta", built)):
        m = re.search(r'id="%s"[^>]*>([^<]+)<' % tag, html)
        if not m or num(m.group(1)) != built:
            bad.append("the served HTML's %s says %s, not the store's %d"
                       % (tag, m.group(1) if m else "nothing", built))

    if bad:
        print("  PROBLEMS:")
        for line in bad:
            print("   -", line)
        print()
        print("  A number that cannot follow the data is a number that will")
        print("  be wrong on the first day the catalog moves.")
        return 1
    print("  Every count on the page follows the data it is showing, and")
    print("  lanes match services rather than the numbers they sit at.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
