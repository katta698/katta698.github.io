#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What "Load the live catalog" leaves behind, and for how long.

Reported as: "when I load live catalog the number changes to 1,599, and
when I close the session and come back it still shows 1,581. I really
don't understand. What does live catalog mean?"

The pull lived in memory for one visit. Closing the tab threw it away and
the shipped snapshot came back, so the page looked like it had forgotten
something it had just been told -- and nothing on screen said whether the
button had written anything anywhere, or for how long.

It now keeps the pull in this browser, and this asserts the three things
that makes true or false. Rather than pulling from AWS (a check that
needs the network, and 1,599 sessions over sixteen requests, is a check
that gets skipped), the kept copy is seeded directly into localStorage --
which is exactly the state a returning visitor arrives in.

  a kept copy is adopted     the page comes up showing the numbers that
                             were pulled, not the ones it shipped with,
                             and says where they came from and that they
                             are kept

  a superseded copy is not   when the morning refresh ships a snapshot
                             taken AFTER the pull, the kept copy is the
                             stale one and must be dropped, not preferred
                             -- the same bug pointing the other way

  an old copy is not         past three days it goes, whatever the
                             snapshot says
"""
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "intelligence", "reinvent2026.json")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("  playwright not installed -- skipping")
    sys.exit(0)

PORT = 8977
URL = "http://127.0.0.1:%d/reinvent-2026/" % PORT
KEY = "ri2026.live"
DROP = 40           # the "pulled" copy is deliberately a different size

READ = """()=>{
  const g = s => { const e = document.querySelector(s);
    return e ? e.textContent.trim() : null; };
  return { total: g('#n-total'), fresh: g('#fresh'),
           all: g('[data-count="all"]'),
           kept: !!localStorage.getItem('ri2026.live') };
}"""


def main():
    store = json.load(io.open(STORE, encoding="utf-8"))
    shipped = len(store["sessions"])
    pulled = json.loads(json.dumps(store))
    pulled["sessions"] = pulled["sessions"][:-DROP]
    want = shipped - DROP

    now = datetime.now(timezone.utc)
    captured = store.get("captured_utc") or (store["captured"] + "T00:00:00Z")
    after_capture = (datetime.strptime(captured, "%Y-%m-%dT%H:%M:%SZ")
                     .replace(tzinfo=timezone.utc) + timedelta(minutes=30))

    cases = [
        ("a copy pulled since the snapshot",
         after_capture.strftime("%Y-%m-%dT%H:%M:%SZ"), want, True),
        ("a copy the morning refresh superseded",
         (after_capture - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         shipped, False),
        ("a copy from last week",
         (now - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         shipped, False),
    ]

    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                           cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    time.sleep(2)
    bad = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            for label, at, expect, adopt in cases:
                ctx = b.new_context(viewport={"width": 1250, "height": 1000})
                pg = ctx.new_page()
                pg.goto(URL, wait_until="domcontentloaded")
                pg.evaluate("""(kept)=>{
                    localStorage.setItem('ri2026.live', JSON.stringify(kept));
                }""", {"at": at, "n": want, "d": pulled})
                pg.reload(wait_until="domcontentloaded")
                pg.wait_for_selector("#browse .card", timeout=30000)
                pg.wait_for_timeout(700)
                got = pg.evaluate(READ)
                num = (got["total"] or "").replace(",", "")
                ok = num == str(expect)
                print("  %-36s shows %-6s expected %-6s %s"
                      % (label, num, expect, "ok" if ok else "WRONG"))
                if not ok:
                    bad.append("%s: the page shows %s, not %s"
                               % (label, num, expect))
                if (got["all"] or "").replace(",", "") != str(expect):
                    bad.append("%s: the Everything tab says %s while the "
                               "header says %s"
                               % (label, got["all"], got["total"]))
                text = (got["fresh"] or "").lower()
                if adopt:
                    for phrase in ("live catalog you loaded",
                                   "kept in this browser"):
                        if phrase not in text:
                            bad.append("%s: the page does not say %r -- a "
                                       "reader cannot tell where these "
                                       "numbers came from" % (label, phrase))
                    if not got["kept"]:
                        bad.append("%s: the kept copy was thrown away"
                                   % label)
                else:
                    if "you loaded" in text:
                        bad.append("%s: the page is still presenting the "
                                   "superseded copy as current" % label)
                    if got["kept"]:
                        bad.append("%s: the stale copy is still in storage "
                                   "and will be adopted again tomorrow"
                                   % label)
                print("     says: %s" % (got["fresh"] or "")[:104])
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
        print("  A button that looks like it saved something, and did not,")
        print("  is worse than one that says it cannot.")
        return 1
    print("  A live pull survives coming back, a superseded one does not,")
    print("  and the page says which it is showing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
