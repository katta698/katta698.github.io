#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Break the announcement pipeline on purpose, and see what notices.

    python scripts/chaos_news.py            # run every experiment
    python scripts/chaos_news.py --only feed_goes_silent

WHY THIS IS NOT JUST MORE TESTS
-------------------------------
check_news.py asks "is the store correct right now". This asks a different
question: "when a realistic thing goes wrong, does anyone find out". Those come
apart badly here, because every failure mode in this pipeline is silent by
construction. A feed that dies returns an empty list, and an empty list is
indistinguishable from a quiet week. Nothing throws.

The failure modes below are not invented. Each one has either already happened
in this repo or is recorded in CLAUDE.md as having happened:

  feed_goes_silent      the GCP compute-engine feed has been frozen since April
                        2020 -- 2,307 days -- while answering HTTP 200 the whole
                        time. 9 of 39 probed GCP feeds were over 60 days behind.
  feed_shape_changes    Google's release notes are parsed by splitting on an
                        <h2 class="release-note-product-title">. A class rename
                        yields a valid document that parses to zero notes.
  interrupted_write     save_month() opens with "w", which truncates before it
                        writes. site-footer.js was destroyed exactly this way on
                        2026-09-03, ending up 0 bytes.
  corrupt_month_file    a half-written or hand-edited jsonl line.
  clock_skew            a feed dating entries in the future. The GCP security
                        bulletin feed gives every entry the feed's generation
                        time rather than its own.

EVERY EXPERIMENT RUNS AGAINST A COPY. The real store under intelligence/data is
never touched; DATA is redirected at a temporary directory for the duration and
restored afterwards, including when an experiment raises.
"""
import argparse
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import datetime
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import news_store as store          # noqa: E402
import check_news                   # noqa: E402

REAL_DATA = store.DATA


@contextlib.contextmanager
def sandbox():
    """A throwaway copy of the store. The real one is never written to."""
    tmp = tempfile.mkdtemp(prefix="chaos-news-")
    dest = os.path.join(tmp, "data")
    shutil.copytree(REAL_DATA, dest)
    store.DATA = dest
    check_news.store.DATA = dest
    try:
        yield dest
    finally:
        store.DATA = REAL_DATA
        check_news.store.DATA = REAL_DATA
        shutil.rmtree(tmp, ignore_errors=True)


def run_guard(checks=None):
    """Run check_news's checks over whatever the sandbox now holds."""
    check_news.problems, check_news.warnings, check_news.notes = [], [], []
    data = check_news.load_all()
    for fn in (checks or [check_news.check_not_empty,
                          check_news.check_feed_silence,
                          check_news.check_no_empty_months,
                          check_news.check_no_bad_lines,
                          check_news.check_freshness,
                          check_news.check_ids_unique,
                          check_news.check_schema,
                          check_news.check_dates_sane,
                          check_news.check_tagging]):
        try:
            fn(data)
        except Exception as exc:                             # noqa: BLE001
            check_news.problems.append("%s raised %s"
                                       % (fn.__name__, type(exc).__name__))
    return list(check_news.problems), list(check_news.warnings)


# ── experiments ─────────────────────────────────────────────────
# Each returns (hypothesis, observed, caught)

def feed_goes_silent(_):
    """One of 19 AWS feeds stops publishing but keeps answering 200."""
    rows = []
    for ym in store.all_months("aws"):
        rows.extend(store.load_month("aws", ym).values())
    # The SMALLEST feed on purpose. Silencing the largest was caught by
    # cloud-level freshness alone, which made the experiment look like a
    # pass while a minor feed could still die unnoticed -- and a minor feed
    # dying quietly is the failure that actually happened to GCP.
    victim = collections.Counter(r["source"] for r in rows).most_common()[-1][0]
    cutoff = (datetime.date.today() - datetime.timedelta(days=400)).isoformat()

    # Simulate: that feed has contributed nothing recent.
    for ym in store.all_months("aws"):
        recs = store.load_month("aws", ym)
        keep = {k: v for k, v in recs.items()
                if not (v["source"] == victim and v["date"] > cutoff)}
        store.save_month("aws", ym, keep)

    probs, warns = run_guard()
    caught = bool(probs) or any(victim in w for w in warns)
    return ("a MINOR dead feed among 19 is noticed",
            "feed %r (smallest) silent 400 days; %d problem(s), %d warning(s)"
            % (victim, len(probs), len(warns)),
            caught)


def all_feeds_die(_):
    """Total outage: nothing new lands for any cloud."""
    old = (datetime.date.today() - datetime.timedelta(days=45)).isoformat()
    for cloud in store.CLOUDS:
        for ym in store.all_months(cloud):
            recs = store.load_month(cloud, ym)
            keep = {k: v for k, v in recs.items() if v["date"] <= old}
            store.save_month(cloud, ym, keep)
    probs, _ = run_guard()
    return ("a total ingest outage is noticed",
            "%d problem(s) reported" % len(probs),
            len(probs) >= 3)


def interrupted_write(_):
    """The process dies between truncate and flush inside save_month."""
    ym = store.all_months("aws")[-1]
    path = os.path.join(store.DATA, "aws", "%s.jsonl" % ym)
    before = len(store.load_month("aws", ym))
    # This is literally what "w" does on open, before any content is written.
    io.open(path, "w", encoding="utf-8").close()
    after = len(store.load_month("aws", ym))
    probs, _ = run_guard()
    return ("an interrupted write cannot silently empty a month",
            "%s went from %d records to %d; guard reported %d problem(s)"
            % (ym, before, after, len(probs)),
            after == before or bool(probs))


def corrupt_month_file(_):
    """A half-written line in the middle of a month file."""
    ym = store.all_months("gcp")[-1]
    path = os.path.join(store.DATA, "gcp", "%s.jsonl" % ym)
    lines = io.open(path, encoding="utf-8").read().splitlines()
    before = len(lines)
    lines.insert(len(lines) // 2, '{"id": "trunc", "cloud": "gcp", "dat')
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    after = len(store.load_month("gcp", ym))
    probs, _ = run_guard()
    return ("a corrupt line does not take the whole month with it",
            "%d line(s) on disk, %d parsed, guard reported %d problem(s)"
            % (before + 1, after, len(probs)),
            after >= before)


def clock_skew(_):
    """A feed starts dating entries in the future."""
    ym = store.all_months("azure")[-1]
    recs = store.load_month("azure", ym)
    ahead = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    for i, r in enumerate(list(recs.values())[:20]):
        r["date"] = ahead
    store.save_month("azure", ym, recs)
    probs, warns = run_guard()
    return ("future-dated records are flagged",
            "20 records dated %s; %d problem(s), %d warning(s)"
            % (ahead, len(probs), len(warns)),
            bool(probs or warns))


EXPERIMENTS = collections.OrderedDict([
    ("feed_goes_silent", feed_goes_silent),
    ("all_feeds_die", all_feeds_die),
    ("interrupted_write", interrupted_write),
    ("corrupt_month_file", corrupt_month_file),
    ("clock_skew", clock_skew),
])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", choices=list(EXPERIMENTS))
    args = ap.parse_args()
    names = args.only or list(EXPERIMENTS)

    print("  Running %d experiment(s) against a COPY of the store.\n"
          "  %s is not modified.\n" % (len(names), REAL_DATA))

    survived = []
    for name in names:
        with sandbox() as box:
            hypothesis, observed, caught = EXPERIMENTS[name](box)
        mark = "CAUGHT " if caught else "MISSED "
        print("  [%s] %s" % (mark, name))
        print("        expect : %s" % hypothesis)
        print("        actual : %s\n" % observed)
        if not caught:
            survived.append(name)

    # Confirm the real store is untouched -- the whole exercise is worthless if
    # a chaos run can damage the thing it is testing.
    assert store.DATA == REAL_DATA
    total = sum(len(store.load_month(c, ym))
                for c in store.CLOUDS for ym in store.all_months(c))
    print("  real store intact: %d records" % total)

    if survived:
        print("\n  %d experiment(s) went UNNOTICED: %s"
              % (len(survived), ", ".join(survived)))
        return 1
    print("\n  every failure was noticed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
