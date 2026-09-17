#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read the Microsoft AI Tour stops off Microsoft's own page into events.json.

    python scripts/import_aitour.py            # show what it would write
    python scripts/import_aitour.py --write    # merge into events.json

Why this exists
---------------
The first pass at this page took nine AI Tour cities off the tour index by
reading the visible carousel. The page actually links thirty-four, and the
missing twenty-five were the ones that answer the question the page is for:
"is one of these near me?" Houston, Mumbai, Bengaluru, Sydney, Tokyo,
Johannesburg, Sao Paulo, Riyadh.

It also stored URLs truncated at sixty characters, because that is how wide
the debug output was. One of them -- Singapore -- pointed at a path that is
not a page: it answered 200 with nothing on it, which is exactly the kind of
"working" link check_events was too weak to catch.

So this reads the anchors themselves rather than the text around them. City,
date and URL come from the SAME element, which is what makes the pairing
trustworthy: paris27 cannot end up next to London's date.

Run by hand, not on a cron, and it does not touch a row a person has edited.
The tour is announced in one go and changes rarely; a daily job rewriting a
curated store is how curation quietly stops meaning anything.
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "intelligence", "events.json")
TOUR = "https://aitour.microsoft.com/"

# The slug is the only reliable name for the twenty-five "notify me" stops --
# those cards carry a date and a button, and no city text of their own. These
# are the ones a slug does not spell the way a person would.
SLUG_CITY = {
    "nyc": "New York", "joburg": "Johannesburg", "saopaulo": "São Paulo",
    "telaviv": "Tel Aviv", "mexicocity": "Mexico City",
    "hongkong": "Hong Kong", "kualalumpur": "Kuala Lumpur",
}
# City -> (country, region). Written out rather than guessed from a library,
# because a wrong country on a page whose entire promise is accuracy is worse
# than no country at all.
PLACE = {
    "Singapore": ("Singapore", "apac"),
    "Paris": ("France", "europe"),
    "London": ("United Kingdom", "europe"),
    "Cologne": ("Germany", "europe"),
    "Philadelphia": ("United States", "north-america"),
    "Mexico City": ("Mexico", "latam"),
    "Dubai": ("United Arab Emirates", "middle-east"),
    "Seattle": ("United States", "north-america"),
    "Utrecht": ("Netherlands", "europe"),
    "Toronto": ("Canada", "north-america"),
    "Madrid": ("Spain", "europe"),
    "Taipei": ("Taiwan", "apac"),
    "Chicago": ("United States", "north-america"),
    "Sydney": ("Australia", "apac"),
    "Johannesburg": ("South Africa", "africa"),
    "Mumbai": ("India", "apac"),
    "Bengaluru": ("India", "apac"),
    "Milan": ("Italy", "europe"),
    "Stockholm": ("Sweden", "europe"),
    "New York": ("United States", "north-america"),
    "São Paulo": ("Brazil", "latam"),
    "Riyadh": ("Saudi Arabia", "middle-east"),
    "Seoul": ("South Korea", "apac"),
    "Tokyo": ("Japan", "apac"),
    "Zurich": ("Switzerland", "europe"),
    "Jakarta": ("Indonesia", "apac"),
    "Miami": ("United States", "north-america"),
    "Copenhagen": ("Denmark", "europe"),
    "Montreal": ("Canada", "north-america"),
    "Brussels": ("Belgium", "europe"),
    "Houston": ("United States", "north-america"),
    "Tel Aviv": ("Israel", "middle-east"),
    "Atlanta": ("United States", "north-america"),
    "Osaka": ("Japan", "apac"),
}

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}

SCRAPE = r"""() => {
  var MON = /(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*20\d\d/;
  var out = [];
  document.querySelectorAll('a[href]').forEach(function (a) {
    if (a.href.indexOf('aitour.microsoft.com') < 0) return;
    if (!/citylanding|notifyme[a-z]+/.test(a.href)) return;
    var box = a.closest('div,li,article') || a;
    var t = (box.innerText || '').trim();
    var m = t.match(MON);
    var lines = t.split('\n').map(function (x) { return x.trim(); })
                 .filter(Boolean);
    var city = lines.filter(function (l) {
      return !MON.test(l) &&
             !/explore|notify|register|more|sponsor|watch/i.test(l);
    })[0] || '';
    out.push({city: city, date: m ? m[0] : '', href: a.href});
  });
  var seen = {}, uniq = [];
  out.forEach(function (o) { if (!seen[o.href]) { seen[o.href] = 1; uniq.push(o); } });
  return uniq;
}"""


def city_from(href, text):
    if text:
        return text
    m = re.search(r"/(?:notifyme)([a-z]+)/", href)
    if not m:
        m = re.search(r"/([a-z]+)27/citylanding", href)
    if not m:
        return ""
    slug = m.group(1)
    return SLUG_CITY.get(slug, slug.capitalize())


def iso(datestr):
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s*(20\d\d)", datestr.strip())
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower())
    if not mon:
        return None
    try:
        return dt.date(int(m.group(3)), mon, int(m.group(2))).isoformat()
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 1600})
        pg = ctx.new_page()
        pg.goto(TOUR, wait_until="load", timeout=90000)
        pg.wait_for_timeout(7000)
        found = pg.evaluate(SCRAPE)
        ctx.close()
        b.close()

    today = dt.date.today().isoformat()
    rows, skipped = [], []
    for f in found:
        city = city_from(f["href"], f["city"])
        start = iso(f["date"])
        if not city or not start:
            skipped.append(f)
            continue
        if city not in PLACE:
            skipped.append(dict(f, why="no country mapped for %r" % city))
            continue
        country, region = PLACE[city]
        rows.append({
            "cloud": "azure",
            "name": "Microsoft AI Tour — %s" % city,
            "type": "tour",
            "start": start, "end": start,
            "city": city, "country": country, "region": region,
            "online": False,
            "url": f["href"],
            "verified": today,
            "announced": True,
            # Structured feed, so the scheduled import counts as
            # verification -- see the note on freshness in
            # check_events.py. Rows read off prose are "read" and
            # only a person may re-stamp those.
            "source": "api",
        })

    rows.sort(key=lambda r: (r["start"], r["city"]))
    print("  %d stop(s) read from %s" % (len(rows), TOUR))
    for r in rows:
        print("     %s  %-14s %-22s" % (r["start"], r["city"], r["country"]))
    if skipped:
        print("\n  %d not imported:" % len(skipped))
        for s in skipped[:10]:
            print("     %s" % str(s)[:120])

    if not args.write:
        print("\n  nothing written; pass --write")
        return 0

    data = json.load(io.open(STORE, encoding="utf-8"))
    others = [e for e in data["events"]
              if not (e.get("url") or "").startswith(
                  "https://aitour.microsoft.com/")]
    data["events"] = others + rows
    data["verified"] = today
    with io.open(STORE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("\n  wrote %d AI Tour row(s), kept %d other row(s)"
          % (len(rows), len(others)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
