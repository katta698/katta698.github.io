#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What the vendor published has to reach the page.

    python scripts/check_status_fields.py

Every other check on the status page asks whether what is ON it is correct.
This one asks whether anything the vendor said is MISSING from it, which is a
different question and the one nothing was asking.

Why it exists
-------------
Reported by a reader: a Google Cloud Storage incident showed no location,
while AWS showed "UAE (me-central-1)" and Azure showed "France Central"; and
clicking Iowa on the map listed incidents from September 2026 and December
2024 but not the one from the previous day.

The store had the answer the whole time -- `"regions": ["us-central1"]`. Three
readers took only the singular `region` / `region_code` that AWS and Azure
use, so every Google incident reached the page with no region at all.

Nothing failed. Nothing could: every check verified that what the page
displayed was accurate, and it was. A dropped field is indistinguishable from
"this incident has no region" unless something compares the page against the
source. That is the whole gap this closes, and it is the same gap
check_events_coverage.py was written for on the events page:

    reconcile against the source -- "is anything missing?" is a different
    question from "is this right?"

What it checks
--------------
For every incident in the live store and the history, where the VENDOR
published a field, the page's own payloads must carry it:

  * the region, in the array the page embeds (the day panel reads it)
  * the region, in timeline-index.json (the map reads it)

The vendor not publishing something is fine and expected -- Azure names a
region for most incidents and not all, AWS leaves two of fifteen blank. The
failure is the page knowing LESS than the store it was built from.

This is deliberately about presence, not correctness. "Is us-central1 really
Iowa" is region_map's job; this only asks whether the page forgot.
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

LIVE = os.path.join(ROOT, "intelligence", "status.json")
HIST = os.path.join(ROOT, "intelligence", "status-history.json")
INDEX = os.path.join(ROOT, "intelligence", "timeline-index.json")
PAGE = os.path.join(ROOT, "intelligence", "status", "index.html")


def published_region(inc):
    """Did the vendor name a region for this incident, in any of its shapes?

    The list first, because that is the shape the bug was about: Google
    publishes `regions` because one incident routinely spans several, and
    reading only the singular field is what dropped them.
    """
    regs = [x for x in (inc.get("regions") or []) if x]
    if regs:
        return regs
    one = inc.get("region_code") or inc.get("region")
    return [one] if one else []


def embedded_payload():
    """The incident array the page carries for its day panel."""
    html = io.open(PAGE, encoding="utf-8", errors="replace").read()
    m = re.search(r'\[\{"g":.*?\}\]', html, re.S)
    if not m:
        return None
    return json.loads(m.group(0))


def main():
    for p in (LIVE, HIST, INDEX, PAGE):
        if not os.path.exists(p):
            print("  %s is missing -- nothing to check" % os.path.basename(p))
            return 0

    live = json.load(io.open(LIVE, encoding="utf-8"))
    hist = json.load(io.open(HIST, encoding="utf-8"))
    index = json.load(io.open(INDEX, encoding="utf-8"))

    store = {}
    for cloud, items in (live.get("clouds") or {}).items():
        for i in items:
            key = i.get("id") or (i.get("title") or "")[:60]
            store[(cloud, key)] = i
    for rec in (hist.get("incidents") or {}).values():
        if not isinstance(rec, dict):
            continue
        cloud = rec.get("cloud")
        key = rec.get("id") or (rec.get("title") or "")[:60]
        if cloud:
            store.setdefault((cloud, key), rec)

    by_page = {}
    payload = embedded_payload()
    if payload is None:
        print("  could not find the incident payload in the page -- the shape")
        print("  changed, and this check cannot see anything. That is a")
        print("  failure, not a pass.")
        return 1
    for r in payload:
        by_page[(r.get("c"), r.get("t") or "")] = r

    by_index = {}
    for r in (index.get("incidents") or []):
        by_index[(r.get("c"), r.get("i") or "")] = r

    problems, checked = [], 0
    counts = {}
    for (cloud, key), inc in store.items():
        regs = published_region(inc)
        counts.setdefault(cloud, [0, 0])
        counts[cloud][0] += 1
        if not regs:
            continue                     # the vendor said nothing; fine
        counts[cloud][1] += 1
        checked += 1

        # The archive index, which is what the map matches a place on.
        rec = by_index.get((cloud, inc.get("id") or ""))
        if rec is not None and not (rec.get("r") or []):
            problems.append(
                "%s %s: the store names %s and timeline-index.json carries no "
                "region, so the map cannot place it"
                % (cloud, (inc.get("title") or "")[:48], ", ".join(regs)))

        # The embedded payload, which is what the day panel prints.
        t = (inc.get("title") or "")[:240]
        pr = by_page.get((cloud, t))
        if pr is not None and not (pr.get("r") or "").strip():
            problems.append(
                "%s %s: the store names %s and the page payload carries no "
                "region, so the day panel shows none"
                % (cloud, t[:48], ", ".join(regs)))

    print("  incidents in the store: %d" % len(store))
    for cloud in sorted(counts):
        tot, withreg = counts[cloud]
        print("     %-6s %4d incident(s), %4d name a region"
              % (cloud, tot, withreg))

    # A check that silently measures nothing passes forever. If no incident
    # anywhere names a region, the readers above have broken, not the data.
    if not checked:
        print("\n  NO incident in the store names a region. That is not a")
        print("  quiet week -- all three vendors publish regions. The reader")
        print("  has broken, and every assertion below would pass on an")
        print("  empty reading.")
        return 1

    if problems:
        print("\n  %d FIELD(S) THE VENDOR PUBLISHED AND THE PAGE DROPPED\n"
              % len(problems))
        for p in problems[:20]:
            print("  - %s" % p)
        if len(problems) > 20:
            print("  ...and %d more" % (len(problems) - 20))
        print("\n  The page is not wrong about what it shows. It knows less")
        print("  than the store it was built from, which looks identical to")
        print("  'the vendor did not say' and is not.")
        return 1

    print("\n  Every region the vendors published reaches the page and the map.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
