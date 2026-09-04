#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Refuse to publish an announcement store that has quietly gone wrong.

Every check here exists because the failure it catches has no symptom. The
store is not rendered by a template and nothing else reads it, so a dead feed,
a stalled ingest or a tagging regression all look exactly like a quiet week.
A stale "what's new" page is worse than no page: it makes a claim about the
present using the past, and a reader cannot tell.

    python scripts/check_news.py            # all checks
    python scripts/check_news.py --strict   # warnings become failures too

Exit codes: 0 fine, 1 something is wrong.

FRESHNESS IS THE ONE THAT MATTERS MOST. It is the only check that notices the
ingest has stopped, and stopping is the default state of anything that has to
be run by hand.
"""
import argparse
import datetime
import io
import json
import os
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import news_store as store          # noqa: E402
import news_tag                     # noqa: E402

JSON_PATH = os.path.join(ROOT, "intelligence", "news.json")
GOLDEN = os.path.join(SCRIPTS, "news_golden.json")

# How many days without a new announcement before something is wrong.
#
# Not one number for all three: AWS publishes every weekday, GCP nearly so, but
# Azure's announcement feed is lumpier and a genuine four-day gap happens. Set
# from the measured cadence, loose enough not to cry wolf over a weekend.
MAX_AGE_DAYS = {"aws": 6, "azure": 10, "gcp": 6}

# Floors, not targets. Measured 2026-09-04 at gcp 100%, aws 97%, azure 82% --
# these sit below that so ordinary drift is quiet and a real regression is not.
MIN_TAGGED_PCT = {"aws": 85, "azure": 65, "gcp": 95}

REQUIRED_FIELDS = ("id", "cloud", "date", "headline", "url", "source",
                   "class", "services", "tag_method", "first_seen")

problems, warnings, notes = [], [], []


def load_all():
    out = {}
    for cloud in store.CLOUDS:
        rows = []
        for ym in store.all_months(cloud):
            rows.extend(store.load_month(cloud, ym).values())
        out[cloud] = rows
    return out


def check_not_empty(data):
    for cloud, rows in data.items():
        if not rows:
            problems.append("%s: the store holds no records at all" % cloud)


def check_freshness(data):
    today = datetime.date.today()
    for cloud, rows in data.items():
        if not rows:
            continue
        newest = max(r["date"] for r in rows)
        age = (today - datetime.date.fromisoformat(newest)).days
        limit = MAX_AGE_DAYS[cloud]
        if age > limit:
            problems.append(
                "%s: newest announcement is %s, %d days old (limit %d). The "
                "ingest has probably stopped, or the feed has. Run: python "
                "scripts/news_store.py ingest" % (cloud, newest, age, limit))
        else:
            notes.append("%s: newest %s (%d day%s old)"
                         % (cloud, newest, age, "" if age == 1 else "s"))


def check_ids_unique(data):
    for cloud, rows in data.items():
        seen = collections.Counter(r.get("id") for r in rows)
        dupes = [i for i, n in seen.items() if n > 1]
        if dupes:
            problems.append("%s: %d duplicate id(s) across month files, e.g. %s"
                            % (cloud, len(dupes), dupes[0]))


def check_schema(data):
    for cloud, rows in data.items():
        missing = collections.Counter()
        for r in rows:
            for f in REQUIRED_FIELDS:
                if f not in r:
                    missing[f] += 1
        if missing:
            problems.append(
                "%s: %s" % (cloud, ", ".join("%d record(s) missing %r" % (n, f)
                                             for f, n in missing.most_common(4))))


def check_dates_sane(data):
    today = datetime.date.today().isoformat()
    for cloud, rows in data.items():
        future = [r for r in rows if r["date"] > today]
        if future:
            # A feed serving a tomorrow-dated item is not impossible across
            # timezones, but a pile of them means a parser is reading the wrong
            # field -- which is exactly the GCP security-bulletin bug, where
            # every entry carried the feed's generation time.
            (problems if len(future) > 5 else warnings).append(
                "%s: %d record(s) dated in the future, newest %s"
                % (cloud, len(future), max(r["date"] for r in future)))


def check_tagging(data):
    for cloud, rows in data.items():
        ann = [r for r in rows if r.get("class") in ("announcement", "release")]
        if not ann:
            problems.append("%s: no records classified as announcements. The "
                            "source-to-class map in news_tag.py is probably "
                            "stale after a feed was renamed." % cloud)
            continue
        tagged = [r for r in ann if r.get("services")]
        pct = 100.0 * len(tagged) / len(ann)
        floor = MIN_TAGGED_PCT[cloud]
        msg = ("%s: %.0f%% of %d announcements tagged (floor %d%%)"
               % (cloud, pct, len(ann), floor))
        if pct < floor:
            problems.append(msg + " -- tagging has regressed")
        else:
            notes.append(msg)


def check_page_matches_store(data):
    """The page is generated; a stale one shows different news than the CLI."""
    if not os.path.isfile(JSON_PATH):
        warnings.append("intelligence/news.json is missing -- run "
                        "scripts/build_news_page.py")
        return
    try:
        payload = json.load(io.open(JSON_PATH, encoding="utf-8"))
    except ValueError as exc:
        problems.append("intelligence/news.json is not valid JSON: %s" % exc)
        return
    items = payload.get("items") or []
    expected = sum(1 for rows in data.values() for r in rows
                   if r.get("class") in ("announcement", "release"))
    if len(items) != expected:
        (problems if abs(len(items) - expected) > 0 else warnings).append(
            "intelligence/news.json holds %d item(s) but the store now has %d "
            "publishable record(s). Re-run scripts/build_news_page.py."
            % (len(items), expected))
    else:
        notes.append("news.json is in step with the store (%d items)" % len(items))


def check_golden():
    """Freeze the hand-checked examples so the tagger cannot regress silently.

    The 42-record review that justified shipping this was done by eye, once.
    That is evidence about a moment, not a guarantee about the future -- these
    cases turn a sample of it into something that runs on every publish.
    """
    if not os.path.isfile(GOLDEN):
        warnings.append("no golden cases at scripts/news_golden.json")
        return
    cases = json.load(io.open(GOLDEN, encoding="utf-8"))["cases"]
    bad = []
    for c in cases:
        rec = {"headline": c["headline"], "product": c.get("product", ""),
               "summary": c.get("summary", ""), "source": c.get("source", "")}
        got, _method = news_tag.tag(c["cloud"], rec)
        if sorted(got) != sorted(c["services"]):
            bad.append("      %-58s\n        expected %s\n        got      %s"
                       % (c["headline"][:58], c["services"], got))
    if bad:
        problems.append("%d of %d golden tagging case(s) changed:\n%s"
                        % (len(bad), len(cases), "\n".join(bad)))
    else:
        notes.append("all %d golden tagging cases still pass" % len(cases))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="treat warnings as failures")
    args = ap.parse_args()

    data = load_all()
    check_not_empty(data)
    check_freshness(data)
    check_ids_unique(data)
    check_schema(data)
    check_dates_sane(data)
    check_tagging(data)
    check_page_matches_store(data)
    check_golden()

    for n in notes:
        print("  ok    %s" % n)
    for w in warnings:
        print("  WARN  %s" % w)
    for p in problems:
        print("  ERROR %s" % p)

    fail = problems or (warnings and args.strict)
    print("\n  %d problem(s), %d warning(s)." % (len(problems), len(warnings)))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
