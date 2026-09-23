#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the whole re:Invent deep audit and report what it found.

    python scripts/audit_reinvent.py
    python scripts/audit_reinvent.py --offline   # skip the AWS comparison

Why this exists, and why it is not in preflight
-----------------------------------------------
Asked before sharing the page with a leadership team: "how do you ensure
my leadership team can rely on this? Can we do some sort of thorough
health check of each and every component?"

preflight's 64 checks assert the page is not BROKEN. Whether what it says
is TRUE is a different question, and it is the one that matters when
somebody searches for a service and gets handed a session. These four
audits answer it the only way that counts -- they drive the real page,
read back what it displays, and re-derive every claim from the store
independently:

  filters  every service, venue, day and format filter, and search,
           against the set computed from the store. A filter that shows
           one wrong session is the failure that embarrasses you.

  planner  every suggested itinerary re-checked for feasibility: no
           overlaps, travel plus buffer honoured on every hop, the first
           session reachable from where you said you would be, a real
           break where the tips claim one, and every "covers X" and
           "fills a gap" label true.

  truth    a random sample compared against the LIVE AWS catalog, field
           by field. Everything else verifies the page against its own
           store; this is the only check that can catch the store itself
           being confidently wrong.

  parts    map counts, the Now view's reachable/unreachable split, the
           announcement-to-session join, and the times in the calendar
           export.

They are excluded from preflight deliberately: two need the network, and
the suite takes minutes. A gate that slow is a gate somebody switches
off. This is the thing you run before handing the page to people whose
opinion of you depends on it being right.
"""
import argparse
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))

PHASES = [
    ("filters", "audit_reinvent_filters.py", False,
     "every filter and search shows exactly the right sessions"),
    ("planner", "audit_reinvent_planner.py", False,
     "every suggested day is attendable and every label is true"),
    ("parts", "audit_reinvent_parts.py", False,
     "map, Now, announcements and calendar agree with the store"),
    ("truth", "audit_reinvent_truth.py", True,
     "a live sample still matches AWS exactly"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="skip the phases that query AWS")
    ap.add_argument("--only", metavar="NAME",
                    help="run one phase by name")
    args = ap.parse_args()

    results, t0 = [], time.time()
    for name, script, needs_net, blurb in PHASES:
        if args.only and args.only != name:
            continue
        if needs_net and args.offline:
            print("  -- %-8s skipped (--offline)" % name)
            results.append((name, None, blurb))
            continue
        print()
        print("=" * 66)
        print("  %s -- %s" % (name.upper(), blurb))
        print("=" * 66)
        started = time.time()
        p = subprocess.run([sys.executable, os.path.join(HERE, script)],
                           cwd=ROOT)
        results.append((name, p.returncode, blurb))
        print("  (%s in %.0fs)" % (name, time.time() - started))

    print()
    print("=" * 66)
    bad = [r for r in results if r[1] not in (0, None)]
    for name, code, blurb in results:
        mark = "skipped" if code is None else ("PASS" if code == 0 else "FAIL")
        print("  %-8s %-8s %s" % (name, mark, blurb))
    print()
    print("  %d phase(s) in %.0fs" % (len(results), time.time() - t0))
    if bad:
        print()
        print("  %d PHASE(S) FAILED. The page is telling somebody something"
              % len(bad))
        print("  that is not true; the output above names which.")
        return 1
    print()
    print("  Nothing the page claims disagrees with the data behind it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
