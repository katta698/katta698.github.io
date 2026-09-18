#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Everything the vendors list is on the page. Not just: everything on the
page is valid.

    python scripts/check_events_coverage.py

Why this exists
---------------
Asked, after the fourth thing was found by a reader rather than by a check:
"how do we ensure these kinds of issues are not seen moving forward?"

Every one of them was the same shape, and it is not the shape anything here
was looking for:

    "AWS publishes no dates"     one probe came back empty and I wrote it
                                 into three files as a fact
    31 summits missing           a guessed directoryId returned totalHits: 0,
                                 which I read as "this API does not serve it"
                                 rather than "wrong name"
    Ignite had no city           the venue is three words after the date that
                                 WAS read off the same line
    Singapore's link dead        a URL truncated at sixty characters by the
                                 width of my own debug output

None of those is a wrong value. Every one is a SILENT ABSENCE: the page
rendered, check_events passed, and the rows simply said less than they should
have. check_events asks "is what is here valid?" -- a question a page missing
thirty events answers perfectly.

So this asks the other question. It goes back to the vendors' own feeds,
counts what they list as upcoming, and requires every one of those to be in
the store. A missing event now fails a check instead of waiting to be noticed.

It reconciles rather than just counting: it names the events that are in the
source and not here, because "31 vs 1" is a puzzle and "AWS lists Summit
Dubai, which you do not have" is an instruction.
"""
import datetime as dt
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
STORE = os.path.join(ROOT, "intelligence", "events.json")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")


def aws_upcoming(today):
    """What AWS's own directory says is still ahead."""
    from import_aws_events import API
    req = urllib.request.Request(API, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read().decode("utf-8"))
    out = []
    for it in data.get("items", []):
        a = it.get("item", {}).get("additionalFields", {})
        d = (a.get("date") or "")[:10]
        try:
            if dt.date.fromisoformat(d) >= today:
                out.append((a.get("title") or "", d))
        except ValueError:
            continue
    return out, data.get("metadata", {}).get("totalHits")


def aitour_upcoming(today):
    """What the AI Tour index still lists as ahead."""
    from playwright.sync_api import sync_playwright
    from import_aitour import SCRAPE, iso, city_from
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 1600})
        pg = ctx.new_page()
        pg.goto("https://aitour.microsoft.com/", wait_until="load",
                timeout=90000)
        pg.wait_for_timeout(7000)
        found = pg.evaluate(SCRAPE)
        ctx.close()
        b.close()
    out = []
    for f in found:
        d = iso(f.get("date") or "")
        if not d:
            continue
        try:
            if dt.date.fromisoformat(d) >= today:
                out.append((city_from(f["href"], f["city"]), d))
        except ValueError:
            continue
    return out, len(found)


def main():
    today = dt.date.today()
    store = json.load(io.open(STORE, encoding="utf-8"))
    have = store.get("events", [])
    problems = []

    # Match on the date plus a distinguishing word, not on the exact name.
    # Vendors re-word titles ("AWS Summit Bogotá 2026" vs "Bogotá Summit")
    # and a check that fails on punctuation teaches people to ignore it.
    def held(date, needle):
        n = (needle or "").lower()
        for e in have:
            if e.get("start") != date:
                continue
            hay = ((e.get("name") or "") + " " + (e.get("city") or "")).lower()
            if not n or n in hay:
                return True
        return False

    # A source that suddenly returns nothing is a broken reader, not an
    # empty calendar.
    #
    # Without this the check has the very hole it was written to close: if
    # Microsoft redesigns the tour index, the scrape finds 0 anchors, the
    # loop below compares 0 events against the store, finds nothing missing,
    # and reports "all present". A pass, produced by reading nothing at all.
    #
    # The floors are deliberately low -- one summit and one stop. The point is
    # not to assert how many events exist, which changes; it is to tell a
    # quiet calendar apart from a reader that has stopped working.
    FLOOR = {"aws": 1, "aitour": 1}

    print("  AWS Summits")
    try:
        aws, total = aws_upcoming(today)
        print("     %s in the directory, %d still ahead" % (total, len(aws)))
        if not total:
            problems.append("AWS's directory returned NOTHING -- 0 summits "
                            "of any date. AWS has not stopped running "
                            "summits; the id or the API has changed, and "
                            "every check below this would pass on an empty "
                            "reading")
        for title, date in aws:
            city = re.sub(r"^AWS Summit\s+", "", title)
            city = re.sub(r"\s*20\d\d$", "", city).strip()
            if not held(date, city.split()[0] if city else ""):
                problems.append("AWS lists %s on %s and the store does not "
                                "have it" % (title, date))
                print("     MISSING  %s  %s" % (date, title[:44]))
            else:
                print("     ok       %s  %s" % (date, title[:44]))
    except Exception as exc:                                # noqa: BLE001
        problems.append("could not read AWS's directory: %s" % str(exc)[:60])
        print("     ??  %s" % str(exc)[:60])

    print("  Microsoft AI Tour")
    try:
        tour, seen = aitour_upcoming(today)
        print("     %d stops linked, %d still ahead" % (seen, len(tour)))
        if seen < FLOOR["aitour"]:
            problems.append("the AI Tour index linked %d stops -- the page "
                            "has changed shape and the reader is finding "
                            "nothing. Comparing nothing against the store "
                            "would report everything present" % seen)
        miss = 0
        for city, date in tour:
            if not held(date, city.split()[0] if city else ""):
                problems.append("the AI Tour lists %s on %s and the store "
                                "does not have it" % (city, date))
                print("     MISSING  %s  %s" % (date, city))
                miss += 1
        if not miss:
            print("     ok       all %d present" % len(tour))
    except Exception as exc:                                # noqa: BLE001
        problems.append("could not read the AI Tour index: %s" % str(exc)[:60])
        print("     ??  %s" % str(exc)[:60])

    print()
    if problems:
        print("  %d THING(S) THE VENDORS LIST AND THIS PAGE DOES NOT\n"
              % len(problems))
        for p in problems[:15]:
            print("  - %s" % p)
        print()
        print("  A page missing thirty events passes every check that only")
        print("  asks whether what is on it is correct.")
        return 1
    print("  Everything the vendors list as upcoming is on the page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
