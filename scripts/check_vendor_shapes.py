#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A field two vendors publish and a third does not is either a fact or a bug.

    python scripts/check_vendor_shapes.py
    python scripts/check_vendor_shapes.py --table    # print the full grid

Asked, after the fourth cosmetic defect found by a reader rather than by a
check: how do we stop missing these.

The pattern behind them
-----------------------
Every one has been the same shape. Three vendors describe the same thing
differently, one reader takes one of the shapes, and the other vendors' data
is silently dropped:

    AWS     "region": "UAE", "region_code": "me-central-1"
    Azure   "region": "France Central"
    Google  "regions": ["us-central1"]          <- a LIST, because one
                                                   incident spans several

Four readers took only the singular form, so every Google incident reached
the page, the map and the archive with no location. Nothing failed, and
nothing could: an absent field renders as nothing, which is exactly what
"the vendor did not say" renders as. The only way to tell those apart is to
compare vendors against each other.

So this prints the grid. For each store, how often each vendor populates each
field. A field at 100% for two vendors and 0% for a third is the signature,
and it is worth exactly one question: is that a real difference between what
the vendors publish, or did we drop it?

Both answers occur, which is why this is a list and not an assertion:

  * REAL. Azure tags announcements "Generally Available" / "Public Preview" /
    "Retirement"; AWS and Google publish no equivalent. Google Cloud Next
    2027 has no date because Google has not announced one.
  * BUG. Google's incident regions, for months.

KNOWN below records the real ones, with the reason. Anything not on that list
fails, and the fix is either a code change or a line here saying why it is
fine. That is the point: a new asymmetry cannot pass silently, and retiring
one costs a sentence.
"""
import argparse
import io
import json
import os
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (label, path, how to reach the records, which key names the vendor)
STORES = [
    ("announcements", "intelligence/news.json", "items", "c"),
    ("events", "intelligence/events.json", "events", "cloud"),
    ("status history", "intelligence/status-history.json", "incidents", "cloud"),
    # The region footprint. Added after az_n turned out to be an AWS-only
    # field while Google published the zone NAMES instead -- the same
    # singular-versus-list split as the incident regions, in a store this
    # check was not looking at.
    ("regions", "intelligence/status/regions.json", "regions", "cloud"),
]

# Asymmetries that are facts about the vendors, not defects in the readers.
# Each needs a reason, because the whole value of this check is that an
# unexplained one stops the build.
KNOWN = {
    ("announcements", "st"):
        "Azure labels each announcement Generally Available / Public Preview "
        "/ Retirement. AWS and Google publish no lifecycle field at all.",
    ("events", "city"):
        "Null until the vendor announces a venue. Google Cloud Next 2027 has "
        "no city yet, and the schema says null rather than a guess.",
    ("events", "country"):
        "Same as city -- unannounced, not dropped.",
    ("events", "start"):
        "Same as city. The events page counts these separately and prints "
        "'awaiting dates' rather than hiding them.",
    ("events", "end"):
        "Same as start.",
    ("events", "note"):
        "A hand-written aside, added where one is useful. Sparse by design "
        "on every vendor, not absent from one.",
    ("status history", "regions"):
        "Google moved to a regions LIST; its older records and both other "
        "vendors use the singular region. inc_regions() in "
        "build_status_page.py reads whichever is present -- this row is the "
        "bug that caused this check to exist, and it is handled.",
    ("status history", "products"):
        "The same split as regions: Google's newer records list products, "
        "everything else sets the singular service.",
    ("status history", "product_count"):
        "Google only, and derived from products.",
    ("status history", "impact"):
        "Google publishes a machine-readable impact; AWS and Azure publish "
        "prose. The disclosure table on the page says so.",
    ("status history", "severity"):
        "Google only. Same disclosure row as impact.",
    ("status history", "first_update"):
        "Google timestamps its first update; the other two do not.",
    ("status history", "region_code"):
        "AWS and Azure carry a machine code beside the place name. Google's "
        "region names ARE codes, so there is nothing separate to carry.",
    ("status history", "service"):
        "Azure publishes no service field -- the service is inside the "
        "incident title. The page's disclosure table rates Azure 0.5 here "
        "rather than pretending otherwise.",
    ("status history", "region"):
        "The inverse of the regions row above: Google sets the LIST and never "
        "the singular field, so 0% here is the shape, not a loss. Verified by "
        "reading the store rather than assumed -- inc_regions() takes "
        "whichever form is present.",
    ("status history", "update"):
        "788 of Google's 795 records were backfilled from gcp-history.json, "
        "which carries update:'' and region:'' on every row -- the original "
        "scrape captured title, date and url and nothing else. Not a reader "
        "dropping it: the source has never had it. Incidents captured since "
        "the schema change carry the full text, which is the 7. Enriching the "
        "788 means re-fetching Google's archive, which is a separate job and "
        "not a bug in the page.",
    ("regions", "az_n"):
        "AWS publishes a zone COUNT; Google publishes the zone NAMES and no "
        "count; Azure publishes neither in this feed. build_clouds_page "
        "reads az_n or the length of the zones list, so Google's 43 are not "
        "lost -- which they were until this row was examined.",
    ("regions", "zones"):
        "The other half of the same split: Google only.",
    ("status history", "tracking"):
        "Azure's own tracking id. The other two have no equivalent.",
    ("status history", "duration"):
        "Derived, and only where an incident has closed.",
}

FLOOR = 80          # "this vendor clearly publishes it"


def records(blob, path):
    cur = blob
    for part in path.split("."):
        cur = cur.get(part, {}) if isinstance(cur, dict) else {}
    if isinstance(cur, dict):
        return [v for v in cur.values() if isinstance(v, dict)]
    return [v for v in cur if isinstance(v, dict)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", action="store_true", help="print the full grid")
    args = ap.parse_args()

    problems, looked = [], 0
    for label, rel, path, vkey in STORES:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print("  %-16s missing, skipped" % label)
            continue
        recs = records(json.load(io.open(p, encoding="utf-8")), path)
        if not recs:
            print("  %-16s no records -- the reader has broken" % label)
            return 1
        groups = defaultdict(list)
        for r in recs:
            groups[str(r.get(vkey) or "?")].append(r)
        vendors = sorted(g for g in groups if g != "?")
        if len(vendors) < 2:
            continue
        keys = sorted({k for r in recs for k in r})

        print("\n  %s  (%d records)" % (label, len(recs)))
        head = "     %-16s" % "field"
        for v in vendors:
            head += "%-10s" % v[:9]
        print(head)
        for k in keys:
            pcts = []
            for v in vendors:
                rs = groups[v]
                n = sum(1 for r in rs if r.get(k) not in (None, "", [], {}))
                pcts.append(100 * n // len(rs) if rs else 0)
            odd = max(pcts) >= FLOOR and min(pcts) == 0
            if not (args.table or odd):
                continue
            row = "     %-16s" % k
            for pc in pcts:
                row += "%-10s" % ("%d%%" % pc)
            if odd:
                looked += 1
                if (label, k) in KNOWN:
                    row += " known"
                else:
                    row += " <-- UNEXPLAINED"
                    problems.append((label, k, dict(zip(vendors, pcts))))
            print(row)

    # A grid that compares nothing passes forever.
    if not looked:
        print("\n  No field differs between vendors anywhere, which is not")
        print("  plausible -- the three publish genuinely different things.")
        print("  The reader has broken rather than the data being uniform.")
        return 1

    print("\n  %d asymmetr%s examined, %d explained in KNOWN"
          % (looked, "y" if looked == 1 else "ies", looked - len(problems)))
    if problems:
        print("\n  %d FIELD(S) ONE VENDOR PUBLISHES AND ANOTHER DOES NOT,"
              " WITH NO REASON RECORDED\n" % len(problems))
        for label, k, pcts in problems:
            print("  - %s.%s  %s" % (label, k, pcts))
        print("\n  Either a reader is dropping it -- which is what happened to")
        print("  Google's incident regions for months, invisibly -- or it is a")
        print("  real difference between the vendors and belongs in KNOWN with")
        print("  a sentence saying so.")
        return 1

    print("  Every one is accounted for.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
