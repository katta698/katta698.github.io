#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every post in a series looks like the other posts in that series.

    python scripts/check_series_pattern.py
    python scripts/check_series_pattern.py --series az
    python scripts/check_series_pattern.py --csv        # one row per post

Why this exists
---------------
Asked for directly: "certain posts are missing a few things and I don't have
time to look at each and every post."

The checks in this repo ask whether a post is correct. None asks whether it is
CONSISTENT with the other posts in its own series, and that is a different
question with its own failure mode: a post published without the verification
badge, or without the diagram every other post in the series carries, is not
wrong about anything. It is just quietly different, and nothing says so.

That class has already cost real time here. On 2026-09-15 four posts rendered
their floating controls inside a hidden element, and 122 of 251 pages lacked
the font preload the other 129 had. Both were "this page differs from its
neighbours", both were invisible to every content check, and both were found by
a reader rather than a script. check_post_shell.py now compares the served
SHELL across posts. This compares the POST: its front matter and its structure.

Compared within a series, never across
--------------------------------------
The series differ from each other by design and it would be wrong to flatten
them. Measured on the corpus this was written against:

    arch / az / gcp   six sections, a decision table, a callout, 15-35 claims
    daily             thirteen sections, no table, no callout
    weekly / azw      eight to eleven sections, an inventory table
    labs              their own shape again

So the reference for every post is the majority of its OWN series. A series of
one has no majority and is reported as unjudgeable rather than silently passed,
which is the distinction check_sources.py already insists on: a count of zero
findings has to be distinguishable from an absence of anything to compare.

What it does not do
-------------------
It has no opinion on whether a difference is wrong. A post can be deliberately
shorter, or deliberately carry no table. It reports the difference and names
what the rest of the series does, and the judgement stays with a person -- the
same reason audit_claims.py is advisory.
"""
import argparse
import csv
import glob
import io
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(ROOT, "posts")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from validate_arch_post import SERIES                              # noqa: E402

DRAFT = re.compile(r"^draft:\s*(true|yes)\s*$", re.M | re.I)

# The three lab series share the week-NN-* namespace, so a file_prefix lookup
# files all of them under whichever SERIES key comes first. The label is the
# only thing that separates them; CLAUDE.md says so, and coverage_report.py
# had to learn the same lesson.
LAB_LABEL = {"AWS Weekly Lab": "awslab",
             "Azure Weekly Lab": "azlab",
             "GCP Weekly Lab": "gcplab"}

# Presence attributes: compared by what most of the series does. Counts are
# reported but only flagged at zero-against-a-series-that-always-has-some,
# because "fewer sections than usual" is an editorial choice and "no sections
# at all" is a broken post.
PRESENCE = [
    ("badge",     lambda fm, b: bool(re.search(r"^verified:", fm, re.M))),
    ("claims",    lambda fm, b: "verified_claims:" in fm),
    ("problem",   lambda fm, b: bool(re.search(r"^problem:", fm, re.M))),
    ("builds",    lambda fm, b: bool(re.search(r"^builds:", fm, re.M))),
    ("catch",     lambda fm, b: bool(re.search(r"^catch:", fm, re.M))),
    ("diagram",   lambda fm, b: bool(re.search(r"<svg|diagrams/", b))),
    ("table",     lambda fm, b: "<table" in b),
    ("callout",   lambda fm, b: 'class="callout"' in b),
    ("code",      lambda fm, b: "<pre" in b),
]

COUNTS = [
    ("n_claims",   lambda fm, b: len(re.findall(r"-\s+claim:", fm))),
    ("n_sections", lambda fm, b: len(re.findall(r"<h2", b))),
    ("n_labels",   lambda fm, b: len(re.findall(r"^\s+-\s+\S", _block(fm, "labels")
                                                or "", re.M))),
]


def _block(fm, key):
    m = re.search(r"^%s:\s*\n((?:\s+-\s+.*\n?)+)" % key, fm, re.M)
    return m.group(1) if m else ""


def series_of(name, fm):
    if name.startswith("week-"):
        for label, key in LAB_LABEL.items():
            if label in fm:
                return key
    for key, spec in SERIES.items():
        if name.startswith(spec["file_prefix"]):
            return key
    return None


def profile(path):
    raw = io.open(path, encoding="utf-8", errors="replace").read()
    if not raw.startswith("---"):
        return None
    end = raw.find("\n---", 3)
    fm, body = raw[:end], raw[end + 4:]
    if DRAFT.search(fm):
        return None
    name = os.path.basename(path)
    key = series_of(name, fm)
    if key is None:
        return None
    p = {"post": name, "series": key}
    for label, fn in PRESENCE:
        p[label] = fn(fm, body)
    for label, fn in COUNTS:
        p[label] = fn(fm, body)
    m = re.search(r"^date:\s*'?\"?(\d{4}-\d{2}-\d{2})", fm, re.M)
    p["date"] = m.group(1) if m else ""
    return p


# How much of a series has to agree before a difference from it is worth
# printing. Without this the report is 180 lines and unusable: 52 of them are
# "has code" / "no code", which is an editorial choice and split roughly evenly
# in most series, and 69 are the problem/builds/catch fields that the Azure
# series adopted partway through. A 60/40 split is not a pattern and a post on
# the minority side of one has not broken anything.
#
# At 0.85 the same corpus reports the differences that are actually anomalous:
# a post without the badge in a series where every other post has one.
CONSENSUS = 0.85


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--series", help="limit to one series key")
    ap.add_argument("--csv", action="store_true",
                    help="one row per post, for a spreadsheet")
    args = ap.parse_args()

    profs = [x for x in (profile(p)
                         for p in sorted(glob.glob(os.path.join(POSTS, "*.html"))))
             if x]
    if args.series:
        profs = [p for p in profs if p["series"] == args.series]
    if not profs:
        print("no posts matched -- this check is not checking anything")
        return 2

    if args.csv:
        w = csv.DictWriter(sys.stdout, fieldnames=list(profs[0].keys()),
                           lineterminator="\n")
        w.writeheader()
        w.writerows(profs)
        return 0

    by = defaultdict(list)
    for p in profs:
        by[p["series"]].append(p)
    order = [k for k in SERIES if k in by]

    # -- 1. inventory ------------------------------------------------------
    print("=" * 96)
    print("SERIES PATTERN — every post against the rest of its own series".center(96))
    print(("%d posts, %d series" % (len(profs), len(by))).center(96))
    print("=" * 96)
    print("\n1. WHAT EACH SERIES IS")
    print("-" * 96)
    print("  %-11s %-28s %5s  %-10s %-10s" % ("key", "label", "posts", "first", "latest"))
    print("-" * 96)
    for k in order:
        ps = by[k]
        ds = [p["date"] for p in ps if p["date"]]
        print("  %-11s %-28s %5d  %-10s %-10s"
              % (k, SERIES[k].get("label", "")[:28], len(ps),
                 min(ds) if ds else "-", max(ds) if ds else "-"))
    print("-" * 96)

    # -- 2. the pattern ----------------------------------------------------
    print("\n2. THE PATTERN OF EACH SERIES  (what most posts in it do)")
    print("-" * 96)
    hdr = "  %-11s %5s " % ("series", "posts")
    hdr += " ".join("%-8s" % lbl[:8] for lbl, _ in PRESENCE)
    hdr += "  %8s %8s" % ("claims~", "sect~")
    print(hdr)
    print("-" * 96)
    modes = {}
    for k in order:
        ps = by[k]
        row = "  %-11s %5d " % (k, len(ps))
        modes[k] = {}
        for lbl, _ in PRESENCE:
            c = Counter(p[lbl] for p in ps)
            mode = c.most_common(1)[0][0]
            modes[k][lbl] = mode
            n = c[mode]
            mark = ("yes" if mode else "no")
            if n != len(ps):
                mark += "*"
            row += "%-8s" % mark
        row += "  %8d %8d" % (median([p["n_claims"] for p in ps]),
                              median([p["n_sections"] for p in ps]))
        print(row)
    print("-" * 96)
    print("  yes/no = what most posts in that series do.  * = not all of them agree.")
    print("  claims~ / sect~ = median claims and median <h2> sections.")

    # -- 3. the odd ones out ----------------------------------------------
    print("\n3. POSTS THAT DIFFER FROM THEIR OWN SERIES")
    print("-" * 96)
    singles = [k for k in order if len(by[k]) < 3]
    findings = []
    for k in order:
        ps = by[k]
        if len(ps) < 3:
            continue            # no majority worth the name
        med_sections = median([p["n_sections"] for p in ps])
        for p in ps:
            diffs = []
            for lbl, _ in PRESENCE:
                agree = sum(1 for q in ps if q[lbl] == modes[k][lbl]) / len(ps)
                if agree < CONSENSUS:
                    continue      # the series has no settled habit here
                if p[lbl] != modes[k][lbl]:
                    diffs.append("%s %s -- %d of %d posts in this series %s"
                                 % ("no" if modes[k][lbl] else "has", lbl,
                                    sum(1 for q in ps if q[lbl] == modes[k][lbl]),
                                    len(ps),
                                    "do" if modes[k][lbl] else "do not"))
            if modes[k]["claims"] and p["n_claims"] == 0 and p["claims"]:
                diffs.append("verified_claims block is empty")
            if med_sections and p["n_sections"] == 0:
                diffs.append("no <h2> sections at all (series median %d)"
                             % med_sections)
            if diffs:
                findings.append((k, p["post"], p["date"], diffs))
    if not findings:
        print("  none -- every post matches the pattern of its series.")
    else:
        cur = None
        for k, post, date, diffs in findings:
            if k != cur:
                print("\n  [%s]  %s" % (k, SERIES[k].get("label", "")))
                cur = k
            print("    %-46s %s" % (post[:46], date))
            for d in diffs:
                print("        - %s" % d)
    print("\n" + "-" * 96)
    print("  %d post(s) differ from their series." % len(findings))
    if singles:
        print("  Not judged -- fewer than 3 posts, so no majority to compare "
              "against: %s" % ", ".join(singles))
    print("  A difference is not automatically a defect. This says what the "
          "rest of the\n  series does; whether this post should match is a "
          "judgement.")
    print("-" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
