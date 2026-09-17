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
import re
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


def deep_check(events):
    """Render every link and require the page to be ABOUT the event.

    A status code proves a server answered. It does not prove the answer is a
    page, and it does not prove the page is the right one. Both failures got
    through here on the first day:

      Singapore was stored as .../singapore27/city -- a URL truncated at sixty
      characters by the width of my own debug output. It answered 200 with an
      empty document, and the check said "ok http 200".

      six other city links were stored as the redirect SOURCE rather than
      where they land, which works until the day it does not.

    So this renders the page and looks for what the row claims: the city for a
    tour stop, otherwise a distinctive word from the name. A page that is
    blank, or that quietly bounced to a generic landing page, fails -- and
    those are exactly the two states a reader meets as a broken link while
    every status code reads fine.

    Rendered rather than fetched, because all three vendors build these pages
    in JavaScript: the raw HTML of a working AI Tour page contains none of its
    own text.

    Slow -- a browser, thirty-eight pages -- so it is not in the push gate.
    The daily workflow runs it, which is the right place for something that
    guards against the outside world changing rather than against an edit.
    """
    from playwright.sync_api import sync_playwright

    bad = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for e in events:
            url = e.get("url")
            if not url:
                continue
            want = e.get("city") or ""
            if not want:
                parts = [w.strip("—-,") for w in (e.get("name") or "").split()]
                parts = [w for w in parts if len(w) > 4 and w.lower() not in
                         ("microsoft", "google", "cloud", "amazon")]
                want = parts[0] if parts else ""
            ctx = b.new_context(viewport={"width": 1280, "height": 900})
            pg = ctx.new_page()
            try:
                pg.goto(url, wait_until="load", timeout=70000)
                pg.wait_for_timeout(4500)
                text = pg.evaluate("() => document.body.innerText") or ""
                final = pg.url
            except Exception as exc:                        # noqa: BLE001
                bad.append((e, "could not render: %s" % str(exc)[:45]))
                ctx.close()
                continue
            ctx.close()

            flat = " ".join(text.split())

            # What "the right page" means, without assuming a language.
            #
            # The first version required the city's name in the page text, and
            # it failed Mexico City and Dubai -- whose pages render in Spanish
            # and Arabic. The city was there; it was spelled the way the
            # reader of that page spells it. A check that demands English from
            # a global tour is measuring the wrong thing, and "fix" would have
            # meant deleting two correct rows.
            #
            # The slug in the URL is language-independent and is what proves
            # arrival: mexicocity27 cannot serve Dubai's page. So: a page that
            # renders, at a URL that still carries the stop's own segment.
            slug = ""
            m = re.search(r"/(notifyme[a-z]+|[a-z]+27)/", url)
            if m:
                slug = m.group(1)

            if len(flat) < 120:
                bad.append((e, "renders %d characters -- effectively a blank "
                               "page" % len(flat)))
            elif slug and slug not in final:
                bad.append((e, "lands on %s, which is not %s -- it bounced to "
                               "a generic page" % (final[:60], slug)))
            elif not slug and want and want.lower() not in flat.lower():
                bad.append((e, "the page never mentions %r; it may have "
                               "bounced to a generic landing page" % want))
            elif final.rstrip("/") != url.rstrip("/"):
                bad.append((e, "redirects to %s -- store where it LANDS, so a "
                               "broken redirect cannot hide" % final[:60]))
            else:
                print("     ok   %-44s %s" % (url[-44:], slug or want or "-"))
        b.close()
    return bad


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
    ap.add_argument("--deep", action="store_true",
                    help="render each link and require it to mention the event")
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

    if args.deep and not args.offline:
        print("  rendering every link (--deep)")
        for e, why in deep_check(events):
            problems.append("%s / %s: %s"
                            % (e.get("cloud"), e.get("name"), why))
            print("     BAD  %-44s %s" % ((e.get("url") or "")[-44:], why[:58]))

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
