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


def configured_feeds(cloud):
    """Feed names the fetcher is configured to read.

    Imported rather than duplicated: a hardcoded copy here would drift from the
    fetchers, and a check that disagrees with the thing it checks is worse than
    no check. Only the SOURCES constant is touched -- nothing is fetched.
    """
    mod = {"aws": "fetch_week", "azure": "fetch_azure_week",
           "gcp": "fetch_week_gcp"}[cloud]
    try:
        m = __import__(mod)
    except Exception:                                        # noqa: BLE001
        return []
    out = []
    for entry in getattr(m, "SOURCES", []):
        # AWS/Azure store (name, url); GCP stores (name, url, kind).
        out.append(entry[0] if isinstance(entry, (list, tuple)) else str(entry))
    return out


def check_feed_silence(data):
    """A single feed going quiet, which cloud-level freshness cannot see.

    Found by a chaos experiment on 2026-09-04. Silencing the largest AWS feed
    was caught; silencing `Containers` -- 10 records of 517 -- was not, because
    the other 18 feeds kept the cloud looking fresh. That is precisely how the
    GCP compute-engine feed stayed frozen for 2,307 days while answering 200.

    Judged against each feed's OWN cadence rather than one number for all of
    them: What's New publishes daily, a service blog can legitimately go a month
    between posts, and a single threshold would either miss the first or cry
    wolf about the second. A feed is quiet when it has been silent for far
    longer than its own historical median gap.

    A warning, not an error. A feed genuinely can be retired, and this must not
    block a publish while somebody decides -- but it must not be invisible
    either, which is the state it was in until now.
    """
    today = datetime.date.today()
    for cloud, rows in data.items():
        by_feed = collections.defaultdict(list)
        for r in rows:
            by_feed[r.get("source", "?")].append(r["date"])

        # A feed with NO records cannot be judged stale -- there is nothing to
        # measure a gap against -- so staleness alone cannot see a feed that
        # vanished, or one that never worked from the day it was added. The
        # configured list is the only place that knows a feed is supposed to
        # exist. A chaos run that removed a feed's records entirely went
        # unnoticed until this compared the two.
        for feed in sorted(set(configured_feeds(cloud)) - set(by_feed)):
            warnings.append(
                "%s/%s: configured as a source but has contributed NOTHING to "
                "the store. Either it has never parsed, or its records were "
                "lost." % (cloud, feed))
        for feed, dates in sorted(by_feed.items()):
            if len(dates) < 4:
                continue            # too little history to judge a cadence
            dates = sorted(set(dates))
            gaps = [(datetime.date.fromisoformat(b)
                     - datetime.date.fromisoformat(a)).days
                    for a, b in zip(dates, dates[1:])]
            gaps.sort()
            median = gaps[len(gaps) // 2] or 1
            silent = (today - datetime.date.fromisoformat(dates[-1])).days
            # Generous: 6x its own median, and never less than 45 days, so a
            # daily feed must miss ~6 days and a monthly one ~6 months.
            limit = max(45, median * 6)
            if silent > limit:
                warnings.append(
                    "%s/%s: nothing since %s, %d days (its median gap is %d, "
                    "so the limit is %d). The feed may have moved or been "
                    "retired -- check with: python scripts/fetch_week%s.py "
                    "--audit"
                    % (cloud, feed, dates[-1], silent, median, limit,
                       "" if cloud == "aws" else
                       ("_gcp" if cloud == "gcp" else "_azure")))


def check_no_empty_months(data):
    """A month file that exists but holds nothing is always wrong.

    Found by a chaos experiment on 2026-09-04: emptying a month file took 101
    AWS records with it and every existing check still passed, because deleting
    September leaves August's newest record only days old and freshness is
    satisfied. save_month now writes atomically so this should not happen --
    this is the check that says so if it does.
    """
    for cloud in store.CLOUDS:
        for ym in store.all_months(cloud):
            if not store.load_month(cloud, ym):
                problems.append(
                    "%s/%s.jsonl exists but parses to zero records. A month "
                    "file is never legitimately empty -- suspect an "
                    "interrupted write." % (cloud, ym))


def check_no_bad_lines(_data):
    """Lines that would not parse. load_month skips them to protect the rest of
    the file; that is the right behaviour and the wrong place to stay quiet."""
    for path, n in sorted(store.BAD_LINES.items()):
        problems.append("%s: %d line(s) could not be parsed and were skipped"
                        % (os.path.relpath(path, ROOT).replace("\\", "/"), n))


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
    check_feed_silence(data)
    check_no_empty_months(data)
    check_no_bad_lines(data)
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
