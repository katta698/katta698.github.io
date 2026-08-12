#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull a complete, deterministic inventory of what AWS published in a date range.

Why this exists
---------------
The AWS Weekly Intelligence post promises a reader that they do not need to
check anywhere else. That promise only holds if the inventory behind it is
complete, and twice it was not.

**Failure 1 — summarisation.** Announcements were originally gathered by asking
a model to read the What's New feed and list what it found. Model summarisation
silently drops items: for the week of 3-7 August 2026 that method captured 42 of
66 announcements. A third of the week was missing, with no error. Fixed by
parsing the raw RSS: every <item>, no judgement, no omissions.

**Failure 2 — an incomplete source list.** Fixing the parsing did not fix the
sources. Only two feeds were read (What's New, News Blog) while AWS publishes
technical detail across a dozen service blogs, and security bulletins were
listed as "NO FEED, check by hand" when a feed exists and was never opened.
Measured on 12 August 2026, that was roughly 170 unread posts. Fixed by
enumerating every source below and parsing all of them.

The lesson behind both: verify the source list, not only the parsing of it. A
source that is absent from this file cannot be noticed as missing at run time.

Usage
-----
    python scripts/fetch_week.py                     # the last 7 days
    python scripts/fetch_week.py 2026-08-03 2026-08-09
    python scripts/fetch_week.py --markdown          # ready to paste into a post
    python scripts/fetch_week.py --audit             # probe every feed, print health

Limits worth knowing
--------------------
The What's New feed is capped at exactly 100 items. Measured 12 August 2026 that
was a **12-day** window, so run this weekly; anything older cannot be recovered
from this source at all. The script detects the risk itself: if the requested
start date is at or before the oldest item the feed still carries, it prints a
TRUNCATION WARNING, because items may have aged out unseen. Do not ignore it.

Events, summits and re:Invent news have no feed and remain a genuine manual
step, printed on every run so the gap stays visible.
"""
import argparse
import collections
import concurrent.futures
import datetime
import email.utils
import io
import sys
import urllib.request
import xml.etree.ElementTree as ET

WHATS_NEW = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"

# Every AWS source with a machine-readable feed. Adding a source here is the
# only way it gets read; there is no discovery. Re-probe with --audit when a
# roundup feels thin, and check the AWS blog index for new blogs periodically.
#
# Security bulletins were previously in MANUAL_SOURCES as "NO FEED". That was
# wrong and never checked — the feed exists and carries ~96 items.
SOURCES = [
    ("What's New",        WHATS_NEW),
    ("News Blog",         "https://aws.amazon.com/blogs/aws/feed/"),
    ("Security Bulletins", "https://aws.amazon.com/security/security-bulletins/feed/"),
    ("Security Blog",     "https://aws.amazon.com/blogs/security/feed/"),
    ("Networking",        "https://aws.amazon.com/blogs/networking-and-content-delivery/feed/"),
    ("Compute",           "https://aws.amazon.com/blogs/compute/feed/"),
    ("Containers",        "https://aws.amazon.com/blogs/containers/feed/"),
    ("Database",          "https://aws.amazon.com/blogs/database/feed/"),
    ("Storage",           "https://aws.amazon.com/blogs/storage/feed/"),
    ("Big Data",          "https://aws.amazon.com/blogs/big-data/feed/"),
    ("DevOps",            "https://aws.amazon.com/blogs/devops/feed/"),
    ("Architecture",      "https://aws.amazon.com/blogs/architecture/feed/"),
    ("Machine Learning",  "https://aws.amazon.com/blogs/machine-learning/feed/"),
    ("Cloud Operations",  "https://aws.amazon.com/blogs/mt/feed/"),
    ("Open Source",       "https://aws.amazon.com/blogs/opensource/feed/"),
    ("HPC",               "https://aws.amazon.com/blogs/hpc/feed/"),
    ("Cost Management",   "https://aws.amazon.com/blogs/aws-cloud-financial-management/feed/"),
    ("Marketplace",       "https://aws.amazon.com/blogs/awsmarketplace/feed/"),
    ("Quantum",           "https://aws.amazon.com/blogs/quantum-computing/feed/"),
]

# Genuinely no feed. Probed 12 August 2026: https://aws.amazon.com/events/feed/
# returns HTTP error. Listed so the gap is visible on every run rather than
# silently absent, and must be checked by hand before publishing a roundup:
#   - Events, summits and re:Invent news   https://aws.amazon.com/events/
MANUAL_SOURCES = ("events / re:Invent",)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def parse(raw):
    """Return [(date, title, link)] sorted newest first."""
    out = []
    for it in ET.fromstring(raw).findall(".//item"):
        pub = it.findtext("pubDate")
        if not pub:
            continue
        out.append((email.utils.parsedate_to_datetime(pub).date(),
                    (it.findtext("title") or "").strip(),
                    (it.findtext("link") or "").strip()))
    return sorted(out, key=lambda r: r[0], reverse=True)


def load(name_url):
    """Fetch and parse one source. Never raises — a dead feed must be reported,
    not crash the run, but it must never look like an empty one either."""
    name, url = name_url
    try:
        return name, parse(fetch(url)), None
    except Exception as exc:                                  # noqa: BLE001
        return name, [], "%s: %s" % (type(exc).__name__, exc)


def gather():
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        return list(pool.map(load, SOURCES))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start", nargs="?", help="YYYY-MM-DD (default: 7 days ago)")
    ap.add_argument("end", nargs="?", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--markdown", action="store_true",
                    help="emit a markdown table per day")
    ap.add_argument("--audit", action="store_true",
                    help="probe every feed and report its health, then exit")
    args = ap.parse_args()

    results = gather()

    if args.audit:
        print("%-20s %6s  %s" % ("SOURCE", "ITEMS", "COVERAGE"))
        for name, rows, err in results:
            if err:
                print("%-20s %6s  BROKEN — %s" % (name, "-", err))
            elif not rows:
                print("%-20s %6d  empty feed" % (name, 0))
            else:
                print("%-20s %6d  %s to %s" % (name, len(rows),
                                               rows[-1][0], rows[0][0]))
        for name in MANUAL_SOURCES:
            print("%-20s %6s  no feed exists — check by hand" % (name, "-"))
        return 1 if any(e for _, _, e in results) else 0

    today = datetime.date.today()
    end = datetime.date.fromisoformat(args.end) if args.end else today
    start = (datetime.date.fromisoformat(args.start) if args.start
             else end - datetime.timedelta(days=6))

    # Report every source explicitly. A source returning nothing must look
    # different from a source that failed, and both must look different from a
    # source that was never consulted — that ambiguity is how the News Blog was
    # missed in the first roundup and the service blogs in every roundup since.
    failures = []
    inrange = {}
    for name, rows, err in results:
        if err:
            failures.append(name)
            print("%-20s: FETCH FAILED — %s" % (name, err), file=sys.stderr)
            continue
        hits = [r for r in rows if start <= r[0] <= end]
        inrange[name] = hits
        print("%-20s: %3d in range  (feed holds %d)" % (name, len(hits), len(rows)),
              file=sys.stderr)
    for name in MANUAL_SOURCES:
        print("%-20s: NO FEED — check by hand" % name, file=sys.stderr)

    # Truncation guard. The What's New feed is a hard 100-item cap. If the
    # oldest item it still carries is not older than the requested start, items
    # inside the range may already have aged out and this inventory is not
    # provably complete.
    wn_all = dict((n, r) for n, r, e in results if not e).get("What's New", [])
    if wn_all:
        oldest = wn_all[-1][0]
        if oldest >= start:
            print("\n*** TRUNCATION WARNING ***", file=sys.stderr)
            print("What's New holds %d items back to %s; you asked from %s."
                  % (len(wn_all), oldest, start), file=sys.stderr)
            print("Items in range may have aged out unseen. This inventory is "
                  "NOT provably complete — do not publish it as one.",
                  file=sys.stderr)
    print(file=sys.stderr)

    rows = inrange.get("What's New", [])
    if not rows and not any(inrange.values()):
        print("Nothing in range across any source.", file=sys.stderr)
        return 1

    by_day = collections.OrderedDict()
    for d, t, l in rows:
        by_day.setdefault(d, []).append((t, l))

    out = io.StringIO()
    if args.markdown:
        for d in sorted(by_day, reverse=True):
            out.write("\n### %s (%d)\n\n" % (d.strftime("%A %d %B %Y"), len(by_day[d])))
            for t, l in by_day[d]:
                out.write("- [%s](%s)\n" % (t, l))
    else:
        out.write("%s to %s — %d announcements\n\n" % (start, end, len(rows)))
        for d in sorted(by_day, reverse=True):
            out.write("%s  (%d)\n" % (d, len(by_day[d])))
            for t, l in by_day[d]:
                out.write("   %s\n      %s\n" % (t, l))
            out.write("\n")

    for name, _ in SOURCES:
        if name == "What's New":
            continue
        hits = inrange.get(name) or []
        if not hits:
            continue
        out.write("\n%s (%d)\n" % (name, len(hits)))
        for d, t, l in hits:
            out.write("   %s  %s\n      %s\n" % (d, t, l))

    sys.stdout.buffer.write(out.getvalue().encode("utf-8"))
    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
