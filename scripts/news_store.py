#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A durable record of every cloud announcement the fetchers have ever seen.

WHY THIS EXISTS
---------------
fetch_week.py, fetch_azure_week.py and fetch_week_gcp.py print a window and
discard it. The vendors' own feeds are short -- AWS What's New holds about 100
items, measured at 12 days on 2026-08-12, and the GCP combined feed truncates at
30 -- so an announcement that is not written down within days of publication
becomes unrecoverable. The weekly roundups capture their own window, in prose,
in HTML; nothing anywhere holds the whole series as data.

That makes an ordinary question unanswerable: "what has changed on S3 lately"
can only reach back as far as the feed still goes.

This module is the missing half. The fetchers stay exactly as they are -- they
already handle the parts that are genuinely hard, and this file deliberately
imports them rather than reimplementing any of it:

  * AWS  gather()      -> [(source, [(date, title, link)], err)]
  * Azure gather()     -> [(source, [(date, title, link)], err)]
  * GCP  gather_ctx()  -> [(source, [(date, product, kind, summary, link, ctx)], err)]

WHY JSONL, PARTITIONED BY MONTH
-------------------------------
Four worktrees publish to one branch. A single store.json would conflict on
every parallel publish and would have to be hand-merged, which is exactly what
the repo's rules forbid for generated files. One file per cloud per month keeps
a day's ingest inside one small file, and line-oriented records mean git can
merge two windows' appends without help.

IDEMPOTENCE
-----------
Ingest is safe to run as often as you like. Records are keyed by a stable hash
of (cloud, date, headline, url), so re-fetching the same feed merges rather than
duplicates. `first_seen` is preserved from the existing record on merge -- it
records when WE saw it, which is not the same as when the vendor published it,
and is the only way to tell a backfilled item from a live one.

WHAT THIS FILE DOES NOT DO
--------------------------
It does not answer questions. Filtering and phrasing belong on top of a complete
store, not inside the thing that fills it -- keeping them apart is what stops a
query bug from corrupting the archive.
"""
import argparse
import datetime
import hashlib
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
DATA = os.path.join(ROOT, "intelligence", "data")

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

CLOUDS = ("aws", "azure", "gcp")


# ── record identity ─────────────────────────────────────────────

def record_id(cloud, date, headline, url, context=""):
    """Stable across runs, so a re-fetch merges instead of duplicating.

    The URL alone is not enough. A GCP release note's link is the day anchor on
    the release-notes page, so an entire day of notes shares one URL -- measured
    at 282 notes across 11 distinct URLs for 17-21 August 2026. The headline has
    to be part of the key or a day of GCP news collapses into eleven records.

    `context` is in the key for the reason CLAUDE.md sets out under the GCP
    dedup rules: same-text/same-product notes are NOT duplicates. Container
    Optimized OS ships one note per milestone, so a single kernel CVE fixed in
    cos-138, cos-125 and cos-121 is three separate notes with byte-identical
    text and the same day anchor. Measured on this store's first ingest: of 120
    id collisions, 82 differed only by context -- 246 rows would have been
    silently dropped, and the count the roundups rest on would have been wrong
    in the direction nobody checks.

    Rows identical INCLUDING context are true duplicates (the same note reached
    by two feeds) and still collapse, which is the behaviour we want.
    """
    raw = "|".join((cloud, str(date), (headline or "").strip(),
                    (url or "").strip(), (context or "").strip()))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _blank(cloud, date, headline):
    return {
        "id": None,
        "cloud": cloud,
        "date": str(date),
        "headline": headline,
        "summary": "",
        "url": "",
        "source": "",
        "product": "",      # GCP product / Azure area, where the feed says
        "kind": "",         # GCP note type: Feature, Security, Change, Fixed...
        "context": "",      # GCP sub-release (a COS milestone, a GKE channel)
        "services": [],     # filled by tag_services(), never by the fetchers
        "first_seen": "",
    }


# ── storage ─────────────────────────────────────────────────────

def _path(cloud, ym):
    return os.path.join(DATA, cloud, "%s.jsonl" % ym)


def load_month(cloud, ym):
    """Records for one cloud-month, keyed by id. Missing file is not an error."""
    p = _path(cloud, ym)
    if not os.path.isfile(p):
        return {}
    out = {}
    with io.open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                # One malformed line must not cost the rest of the month.
                continue
            if r.get("id"):
                out[r["id"]] = r
    return out


def save_month(cloud, ym, records):
    """Write one cloud-month, sorted so the file is stable between runs.

    A stable order matters more than it looks: without it every ingest would
    rewrite the whole file in a new order and every run would show as a large
    diff, which makes a real change impossible to see in review.
    """
    p = _path(cloud, ym)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    rows = sorted(records.values(),
                  key=lambda r: (r.get("date", ""), r.get("headline", ""),
                                 r.get("id", "")))
    with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows)


def merge(existing, incoming, seen_on):
    """Fold incoming records into existing. Returns (added, updated).

    Deliberately conservative: an existing record keeps its first_seen and any
    services already tagged on it. A later fetch of the same announcement can
    enrich empty fields but must never blank a populated one -- feeds do
    occasionally return a thinner version of a row they served fully yesterday.
    """
    added = updated = 0
    for r in incoming:
        rid = r["id"]
        if rid not in existing:
            r["first_seen"] = r.get("first_seen") or seen_on
            existing[rid] = r
            added += 1
            continue
        cur = existing[rid]
        changed = False
        for k, v in r.items():
            if k in ("id", "first_seen", "services"):
                continue
            if v and not cur.get(k):
                cur[k] = v
                changed = True
        updated += changed
    return added, updated


# ── ingest from the live feeds ──────────────────────────────────

def _in_range(d, start, end):
    return (start is None or d >= start) and (end is None or d <= end)


def ingest_aws(start=None, end=None):
    import fetch_week
    out = []
    errors = []
    for source, rows, err in fetch_week.gather():
        if err:
            errors.append("aws/%s: %s" % (source, err))
            continue
        for date, title, link in rows:
            if not _in_range(date, start, end):
                continue
            r = _blank("aws", date, title)
            r["url"] = link
            r["source"] = source
            r["id"] = record_id("aws", date, title, link)
            out.append(r)
    return out, errors


def ingest_azure(start=None, end=None):
    import fetch_azure_week
    out = []
    errors = []
    for source, rows, err in fetch_azure_week.gather():
        if err:
            errors.append("azure/%s: %s" % (source, err))
            continue
        for date, title, link in rows:
            if not _in_range(date, start, end):
                continue
            r = _blank("azure", date, title)
            r["url"] = link
            r["source"] = source
            r["id"] = record_id("azure", date, title, link)
            out.append(r)
    return out, errors


def ingest_gcp(start=None, end=None):
    """GCP carries more per row, and all of it is worth keeping.

    gather_ctx() rather than gather(): the context field is the sub-release a
    note sits under, and it is the only thing that makes a run of identically
    worded Container-Optimized-OS notes explainable rather than merely
    repetitive. build_weekly_inventory_gcp.py already depends on it.
    """
    import fetch_week_gcp
    out = []
    errors = []
    # 4-tuple, unlike AWS and Azure: GCP's loader also returns the FEED kind
    # (daynotes / bulletin / gkebull / rss), because one cloud needs four
    # different parsers. Every parser is normalised to the same 6-tuple row by
    # _pad() on the way out, so only the outer shape differs.
    for source, feed_kind, rows, err in fetch_week_gcp.gather_ctx():
        if err:
            errors.append("gcp/%s: %s" % (source, err))
            continue
        for date, product, kind, summary, link, ctx in rows:
            if not _in_range(date, start, end):
                continue
            # The product+summary IS the headline for GCP -- there is no title
            # field in a release note, only a product heading and a body.
            headline = ("%s: %s" % (product, summary)).strip(": ")
            r = _blank("gcp", date, headline)
            r["summary"] = summary
            r["url"] = link
            r["source"] = source
            r["product"] = product
            r["kind"] = kind
            r["context"] = ctx
            r["id"] = record_id("gcp", date, headline, link, ctx)
            out.append(r)
    return out, errors


INGEST = {"aws": ingest_aws, "azure": ingest_azure, "gcp": ingest_gcp}


def ingest(clouds=CLOUDS, start=None, end=None, dry_run=False):
    seen_on = datetime.date.today().isoformat()
    summary = []
    all_errors = []
    for cloud in clouds:
        rows, errors = INGEST[cloud](start, end)
        all_errors.extend(errors)
        by_month = {}
        for r in rows:
            by_month.setdefault(r["date"][:7], []).append(r)
        added = updated = 0
        for ym, group in sorted(by_month.items()):
            existing = load_month(cloud, ym)
            a, u = merge(existing, group, seen_on)
            added += a
            updated += u
            if not dry_run:
                save_month(cloud, ym, existing)
        summary.append((cloud, len(rows), added, updated, sorted(by_month)))
    return summary, all_errors


# ── reporting ───────────────────────────────────────────────────

def all_months(cloud):
    d = os.path.join(DATA, cloud)
    if not os.path.isdir(d):
        return []
    return sorted(f[:-6] for f in os.listdir(d) if f.endswith(".jsonl"))


def stats():
    print("  %-6s %-8s %-12s %s" % ("CLOUD", "RECORDS", "MONTHS", "COVERAGE"))
    total = 0
    for cloud in CLOUDS:
        months = all_months(cloud)
        n = 0
        lo = hi = None
        for ym in months:
            recs = load_month(cloud, ym)
            n += len(recs)
            for r in recs.values():
                d = r.get("date", "")
                lo = d if lo is None or d < lo else lo
                hi = d if hi is None or d > hi else hi
        total += n
        cover = ("%s .. %s" % (lo, hi)) if lo else "(empty)"
        print("  %-6s %-8d %-12s %s" % (cloud, n, len(months), cover))
    print("\n  total records: %d" % total)
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")

    p_in = sub.add_parser("ingest", help="fetch the live feeds and store them")
    p_in.add_argument("--cloud", choices=CLOUDS, action="append",
                      help="limit to one cloud (repeatable); default all three")
    p_in.add_argument("--since", help="YYYY-MM-DD, ignore anything older")
    p_in.add_argument("--dry-run", action="store_true",
                      help="report what would be stored, write nothing")

    sub.add_parser("stats", help="what the store currently holds")

    args = ap.parse_args()
    if args.cmd == "stats":
        stats()
        return 0

    if args.cmd != "ingest":
        ap.print_help()
        return 2

    start = (datetime.date.fromisoformat(args.since) if args.since else None)
    clouds = tuple(args.cloud) if args.cloud else CLOUDS

    print("Fetching %s%s ..." % (", ".join(clouds),
                                 " since %s" % start if start else ""))
    summary, errors = ingest(clouds, start=start, dry_run=args.dry_run)

    print("\n  %-6s %-8s %-8s %-8s %s"
          % ("CLOUD", "FETCHED", "NEW", "ENRICHED", "MONTHS"))
    for cloud, fetched, added, updated, months in summary:
        print("  %-6s %-8d %-8d %-8d %s"
              % (cloud, fetched, added, updated, ", ".join(months) or "-"))

    if errors:
        # A dead feed is reported, never silently treated as an empty one --
        # the same rule the fetchers themselves follow.
        print("\n  %d feed(s) failed:" % len(errors))
        for e in errors:
            print("    %s" % e)

    if args.dry_run:
        print("\n  dry run -- nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
