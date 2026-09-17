#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read AWS Summits from AWS's own directory API into events.json.

    python scripts/import_aws_events.py          # show what it would write
    python scripts/import_aws_events.py --write

Why this exists
---------------
Because the claim this page was built on was wrong, twice, and a reader found
both in about a minute.

I reported that AWS publishes nothing machine-readable about its events, and
listed re:Invent and the Summits with no dates on that basis. Then:

  re:Invent's page says "Join us Nov. 30 - Dec. 4 in Las Vegas", and its TITLE
  says "AWS re:Invent 2026 | ... | Nov 30-Dec 4". My patterns all required a
  four-digit year next to the day, so a date with the year in the title and
  the days in the sentence matched nothing at all.

  The Summits page lists 31 summits with dates, venues and links -- served by
  aws.amazon.com/api/dirs/items/search, the same directories API I had tested
  and declared unused. I had guessed the directoryId, got totalHits: 0, and
  read that as "not served by this API" rather than "wrong id". The real one
  is events-cards-interactive-summits-cards-interactive-events-summits-hub,
  which no amount of guessing would have produced -- it comes from watching
  the page make the request.

Both are the same mistake: I proved a negative from one probe and wrote it
into three files as a fact. Checking "is there an API" is not the same as
checking "did I ask it the right question".

Only events from today onward are imported. The store's whole discipline is
that every row is re-verified within 30 days, and rows for summits that
happened in April cannot be kept honest and are of no use to a reader.
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "intelligence", "events.json")

API = ("https://aws.amazon.com/api/dirs/items/search"
       "?item.directoryId=events-cards-interactive-summits-cards-interactive"
       "-events-summits-hub&item.locale=en_US"
       "&sort_by=item.additionalFields.publishedDate&sort_order=asc&size=100")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

# City -> (country, region). Written out rather than inferred, for the reason
# in import_aitour.py: a wrong country on a page whose promise is accuracy is
# worse than no country.
PLACE = {
    "Bogotá": ("Colombia", "latam"),
    "Jakarta": ("Indonesia", "apac"),
    "Ciudad de México": ("Mexico", "latam"),
    "Johannesburg": ("South Africa", "africa"),
    "Zurich": ("Switzerland", "europe"),
    "São Paulo": ("Brazil", "latam"),
    "Tel Aviv": ("Israel", "middle-east"),
    "Dubai": ("United Arab Emirates", "middle-east"),
    "Paris": ("France", "europe"),
    "Bengaluru": ("India", "apac"),
    "London": ("United Kingdom", "europe"),
    "Singapore": ("Singapore", "apac"),
    "Warsaw": ("Poland", "europe"),
    "Stockholm": ("Sweden", "europe"),
    "Sydney": ("Australia", "apac"),
    "Seoul": ("South Korea", "apac"),
    "Hamburg": ("Germany", "europe"),
    "Amsterdam": ("Netherlands", "europe"),
    "Mumbai": ("India", "apac"),
    "Bangkok": ("Thailand", "apac"),
    "Milano": ("Italy", "europe"),
    "Toronto": ("Canada", "north-america"),
    "Madrid": ("Spain", "europe"),
    "Los Angeles": ("United States", "north-america"),
    "New York City": ("United States", "north-america"),
    "Hong Kong": ("Hong Kong", "apac"),
    "Shanghai": ("China", "apac"),
    "Japan": ("Japan", "apac"),
    "Washington, D.C.": ("United States", "north-america"),
    "Taipei": ("Taiwan", "apac"),
    "India Online": (None, "online"),
}


def fetch():
    req = urllib.request.Request(API, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def absolute(link):
    link = (link or "").strip()
    if not link:
        return "https://aws.amazon.com/events/summits/"
    if link.startswith("//"):
        return "https:" + link
    if link.startswith("/"):
        return "https://aws.amazon.com" + link
    return link


def city_of(title):
    c = re.sub(r"^AWS Summit\s+", "", title or "").strip()
    c = re.sub(r"\s*20\d\d$", "", c).strip()
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    data = fetch()
    items = data.get("items", [])
    today = dt.date.today()
    print("  %s summit(s) in AWS's directory"
          % data.get("metadata", {}).get("totalHits"))

    rows, past, unmapped = [], 0, []
    for it in items:
        a = it.get("item", {}).get("additionalFields", {})
        date = (a.get("date") or "")[:10]
        try:
            when = dt.date.fromisoformat(date)
        except ValueError:
            continue
        if when < today:
            past += 1
            continue
        city = city_of(a.get("title"))
        if city not in PLACE:
            unmapped.append(city)
            continue
        country, region = PLACE[city]
        online = "Virtual" in (a.get("badge") or "")
        rows.append({
            "cloud": "aws",
            "name": a.get("title"),
            "type": "summit",
            "start": date, "end": date,
            "city": None if online else city,
            "country": country,
            "region": region,
            "online": online,
            # ctaLink is relative -- "/events/summits/dubai/". Stored as-is
            # it is not a link at all once the page is served from this
            # domain, and check_events would have called it "not on an aws
            # domain" rather than "not a URL", which is the wrong complaint.
            "url": absolute(a.get("ctaLink")),
            "verified": today.isoformat(),
            "announced": True,
            # Structured feed, so the scheduled import counts as
            # verification -- see the note on freshness in
            # check_events.py. Rows read off prose are "read" and
            # only a person may re-stamp those.
            "source": "api",
        })

    rows.sort(key=lambda r: r["start"])
    print("  %d upcoming, %d already past (not imported)" % (len(rows), past))
    for r in rows:
        print("     %s  %-34s %s" % (r["start"], r["name"][:34], r["url"][:48]))
    if unmapped:
        print("  no country mapped for: %s" % ", ".join(sorted(set(unmapped))))

    if not args.write:
        print("\n  nothing written; pass --write")
        return 0

    store = json.load(io.open(STORE, encoding="utf-8"))
    # Drop the old placeholder row and any summit previously imported.
    keep = [e for e in store["events"]
            if not (e.get("cloud") == "aws" and e.get("type") == "summit")]
    store["events"] = keep + rows
    store["verified"] = today.isoformat()
    with io.open(STORE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(store, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("\n  wrote %d summit row(s), kept %d other row(s)"
          % (len(rows), len(keep)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
