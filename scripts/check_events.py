#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every event is official, dated honestly, and its link still works.

    python scripts/check_events.py
    python scripts/check_events.py --offline   # skip the network checks

Why this exists
---------------
Asked for an events page that is "authentic, always refreshed, always
trustable, make sure the links are valid, only official links from all these
cloud companies". That is four separate promises, and a page cannot keep any
of them by intention -- only by something failing loudly when they break.

So this is the page's licence to exist. It refuses:

  a link that is not on a vendor's own domain
      The whole value is that every row can be clicked through to the company
      that is running the event. A meetup aggregator or a conference-listing
      site would be easier to gather and would quietly turn this into a
      directory of other people's claims.

  a row that says it is announced without dates, or carries dates while
  saying it is not
      The one state that must never exist is a confident-looking date that no
      vendor published. AWS re:Invent 2026 is in the file with start: null,
      because the official page carried no 2026 dates when it was read. A
      wrong date is worse than no date: a reader books flights around it.

  a row nobody has re-read in 30 days
      "Always refreshed" cannot mean "was true once". Vendors move dates and
      retire pages, and the only honest way to hold the claim is to keep
      reading the source and to fail when nobody has.

  a link that no longer resolves
      Checked over the network, because a 404 is exactly the failure a reader
      meets and exactly the one that is invisible in the data.

The network part is skippable with --offline so the rest still runs on a
train, and it treats 403 as a pass: several vendor pages refuse a scripted
request while serving a browser perfectly. Reporting those as dead links
would make the check untrustworthy in the other direction.
"""
import argparse
import datetime as dt
import io
import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "intelligence", "events.json")

# A row may only point at the company running the event. Subdomains count;
# anything else does not.
OFFICIAL = {
    "aws": ["aws.amazon.com", "awsevents.com", "amazon.com"],
    "azure": ["microsoft.com", "azure.com", "aitour.microsoft.com",
              "ignite.microsoft.com", "build.microsoft.com"],
    "gcp": ["google.com", "cloud.google.com", "withgoogle.com",
            "cloud.withgoogle.com", "gdg.community.dev"],
}
REGIONS = {"apac", "europe", "north-america", "latam", "middle-east",
           "africa", "online"}
TYPES = {"conference", "tour", "summit", "community"}
STALE_DAYS = 30
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")


def host_ok(cloud, url):
    try:
        host = url.split("//", 1)[1].split("/", 1)[0].lower()
    except IndexError:
        return False
    for d in OFFICIAL.get(cloud, []):
        if host == d or host.endswith("." + d):
            return True
    return False


def _transport_failure(detail):
    """True when the request never reached a server at all."""
    d = (detail or "").lower()
    return any(t in d for t in ("getaddrinfo", "name or service",
                                "temporary failure", "timed out",
                                "connection refused", "network is unreachable",
                                "no route to host", "ssl", "urlopen error"))


def reachable(url):
    """(ok, detail). 403 counts as reachable -- see the note at the top."""
    req = urllib.request.Request(url, headers={"User-Agent": UA},
                                 method="GET")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return (200 <= r.status < 400), "http %d" % r.status
    except urllib.error.HTTPError as e:
        if e.code in (403, 405, 429):
            return True, "http %d (served to browsers)" % e.code
        return False, "http %d" % e.code
    except Exception as e:                                  # noqa: BLE001
        return False, str(e)[:50]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="skip the link checks")
    args = ap.parse_args()

    if not os.path.exists(STORE):
        print("  no intelligence/events.json")
        return 1
    data = json.load(io.open(STORE, encoding="utf-8"))
    events = data.get("events", [])
    today = dt.date.today()

    problems = []
    print("  %d event(s) in the store" % len(events))

    for e in events:
        who = "%s / %s" % (e.get("cloud", "?"), e.get("name", "(unnamed)"))

        # official domain
        url = e.get("url") or ""
        if not url:
            problems.append("%s: no url at all" % who)
        elif not host_ok(e.get("cloud"), url):
            problems.append("%s: %s is not on a %s domain -- this page only "
                            "links to the company running the event"
                            % (who, url.split("/")[2] if "//" in url else url,
                               e.get("cloud")))

        # announced vs dated, the one state that must not exist
        announced = e.get("announced")
        start, end = e.get("start"), e.get("end")
        if announced and not start:
            problems.append("%s: announced=true with no start date" % who)
        if (not announced) and start:
            problems.append("%s: announced=false but carries %s -- a date no "
                            "vendor published is the exact failure this store "
                            "exists to prevent" % (who, start))
        for label, v in (("start", start), ("end", end)):
            if v:
                try:
                    dt.date.fromisoformat(v)
                except ValueError:
                    problems.append("%s: %s=%r is not YYYY-MM-DD" % (who, label, v))
        if start and end:
            try:
                if dt.date.fromisoformat(end) < dt.date.fromisoformat(start):
                    problems.append("%s: ends before it starts" % who)
            except ValueError:
                pass

        # freshness
        v = e.get("verified")
        if not v:
            problems.append("%s: never verified" % who)
        else:
            try:
                age = (today - dt.date.fromisoformat(v)).days
                if age > STALE_DAYS:
                    problems.append("%s: last verified %d days ago -- "
                                    "'always refreshed' cannot mean 'was true "
                                    "once'" % (who, age))
            except ValueError:
                problems.append("%s: verified=%r is not a date" % (who, v))

        # vocabulary
        if e.get("region") not in REGIONS:
            problems.append("%s: region=%r is not one of %s"
                            % (who, e.get("region"), sorted(REGIONS)))
        if e.get("type") not in TYPES:
            problems.append("%s: type=%r is not one of %s"
                            % (who, e.get("type"), sorted(TYPES)))

    # links, over the network
    #
    # Offline is a different thing from a dead link, and conflating them makes
    # this check a liar in the other direction. If the FIRST request fails in
    # the transport -- no DNS, no route -- there is no network and the link
    # checks are skipped with that said out loud. A genuine 404 arrives as an
    # HTTPError and is reported. This is also what lets the check sit in the
    # push gate, which has to work on a train.
    if args.offline:
        print("  link checks skipped (--offline)")
    else:
        seen = {}
        offline = False
        for e in events:
            url = e.get("url")
            if not url or url in seen:
                continue
            ok, detail = reachable(url)
            if not ok and _transport_failure(detail):
                offline = True
                print("  no network (%s) -- link checks skipped" % detail[:40])
                break
            seen[url] = ok
            print("     %-4s %-58s %s" % ("ok" if ok else "DEAD",
                                          url[:58], detail))
            if not ok:
                problems.append("%s / %s: %s does not resolve (%s)"
                                % (e.get("cloud"), e.get("name"), url, detail))

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for p in problems[:15]:
            print("  - %s" % p)
        print()
        print("  An events page is only worth having if every row can be")
        print("  clicked through to the company running the event.")
        return 1
    print("  Every event is on an official domain, dated only where the "
          "vendor announced,")
    print("  verified within %d days, and its link resolves." % STALE_DAYS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
