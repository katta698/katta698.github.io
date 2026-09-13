#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One page saying how far the factual checks actually reach across the corpus.

    python scripts/coverage_report.py
    python scripts/coverage_report.py --csv   # same numbers, machine-readable

Why this exists
---------------
Every checker in `scripts/` reports on the posts it can see, and each one sees a
different set. `check_assertions.py` scans 185 of 238 posts and says "Checked
185 post(s)"; `check_sources.py` scans all 238 but has topic rules for two
series; `audit_claims.py` reports a traced-figure percentage per post and no
total. Read any one of them and the corpus looks covered. Read them together
and it does not.

That gap is not hypothetical. `check_sources.py` once held an AWS-only rule
while reporting a clean result for 31 Azure posts -- a green light that meant
"nothing was tested" -- and Azure Architecture #31 went out through it. The
lesson written down at the time was that a count of zero findings has to be
distinguishable from an absence of rules. This file does that for the corpus as
a whole rather than one checker at a time.

**It reports coverage, never correctness.** A post can sit in every green column
here and still be wrong: these checks match patterns and compare figures against
pages, and none of them reads a post for meaning. What the report can tell you
is where nothing is looking.
"""
import argparse
import csv
import glob
import io
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(ROOT, "posts")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from validate_arch_post import SERIES                              # noqa: E402
from audit_claims import audit                                     # noqa: E402
import check_assertions as ca                                      # noqa: E402
import check_sources as cs                                         # noqa: E402

UNCLASSIFIED = "(no series)"

# How stale a verification may be before it stops meaning much. 180 days is the
# threshold validate_arch_post.py already warns at; kept identical on purpose so
# two tools do not disagree about the same word.
STALE_DAYS = 180


# The three lab series share one slug namespace -- the AWS labs are week-NN-*
# and the GCP series began at week-01-gcp-landing-zone -- so file_prefix cannot
# tell them apart. SERIES lists awslab, azlab and gcplab all on "week-", and a
# first-match lookup files every lab post under whichever key comes first,
# reporting 26 AWS labs and zero Azure or GCP ones. The label is the only thing
# that distinguishes them; CLAUDE.md says so and _week_num() in sync_blog.py has
# the same blind spot for the same reason.
LAB_LABEL = {
    "AWS Weekly Lab": "awslab",
    "Azure Weekly Lab": "azlab",
    "GCP Weekly Lab": "gcplab",
}


def series_of(name, front=""):
    if name.startswith("week-"):
        for label, key in LAB_LABEL.items():
            if label in front:
                return key
    for key, spec in SERIES.items():
        if name.startswith(spec["file_prefix"]):
            return key
    return UNCLASSIFIED


def front_matter(path):
    raw = io.open(path, encoding="utf-8").read()
    if not raw.startswith("---"):
        return "", raw
    end = raw.find("\n---", 3)
    return raw[:end], raw[end + 4:]


def parse_date(text, key):
    m = re.search(r"^%s:\s*'?\"?(\d{4}-\d{2}-\d{2})" % key, text, re.M)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


DRAFT_RE = re.compile(r"^draft:\s*(true|yes)\s*$", re.M | re.I)


def collect():
    """Every file in posts/, with drafts marked rather than dropped.

    The two counts differ and the difference matters in a report: posts/ holds
    238 files, one of which carries `draft: true`, so the published corpus is
    237. Quoting the file count as the post count overstates what is live by
    one and, worse, silently averages an unpublished draft into every coverage
    percentage below it.
    """
    rows = []
    for path in sorted(glob.glob(os.path.join(POSTS, "*.html"))):
        name = os.path.basename(path)
        front, _ = front_matter(path)
        info = audit(path) or {}
        rows.append({
            "post": name,
            "series": series_of(name, front),
            "draft": bool(DRAFT_RE.search(front)),
            "date": parse_date(front, "date"),
            "verified": parse_date(front, "verified"),
            "badged": bool(info.get("badged")),
            "claims": info.get("claims", 0),
            "derives": front.count("derive:"),
            "figures": info.get("figures", 0),
            "covered": info.get("covered", 0),
        })
    return rows


def flags_by_post():
    """Outstanding advisory findings, per post, from check_assertions."""
    out = defaultdict(lambda: defaultdict(int))
    for path in sorted(glob.glob(os.path.join(POSTS, "*.html"))):
        name = os.path.basename(path)
        if ca.series_of(name) is None:
            continue
        _, errors, notes, _ = ca.check(path, False)
        for kind, _sentence in notes:
            out[name][kind] += 1
        if errors:
            out[name]["code defect"] += len(errors)
    return out


def source_rule_count(key):
    """How many topic rules check_sources.py holds for a series."""
    rules = getattr(cs, "TOPIC_RULES", {})
    n = len(rules.get(key, []))
    # The AWS pricing->docs rule is not in TOPIC_RULES; it is the module's
    # built-in and applies to every series whose vendor is AWS.
    spec = SERIES.get(key) or {}
    if spec.get("vendor", "").lower().startswith("aws"):
        n += 1
    return n


def pct(a, b):
    return 0.0 if not b else 100.0 * a / b


def bar(value, width=22):
    filled = int(round(value / 100.0 * width))
    return "#" * filled + "." * (width - filled)


def table(title, headers, rows, aligns=None):
    aligns = aligns or ["<"] * len(headers)
    widths = [len(h) for h in headers]
    for r in rows:
        for i, c in enumerate(r):
            widths[i] = max(widths[i], len(str(c)))
    line = "  ".join("-" * w for w in widths)
    print("\n" + title)
    print(line)
    print("  ".join(("%-*s" % (widths[i], h)) for i, h in enumerate(headers)))
    print(line)
    for r in rows:
        cells = []
        for i, c in enumerate(r):
            cells.append(("%*s" if aligns[i] == ">" else "%-*s") % (widths[i], c))
        print("  ".join(cells))
    print(line)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", action="store_true",
                    help="emit the per-post rows as CSV instead of the report")
    args = ap.parse_args()

    everything = collect()
    drafts = [r for r in everything if r["draft"]]
    # Coverage is reported on what is published. A draft is not a gap.
    rows = [r for r in everything if not r["draft"]]
    flags = flags_by_post()
    today = datetime.now().date()

    if args.csv:
        w = csv.DictWriter(sys.stdout, fieldnames=list(rows[0].keys()),
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        return 0

    by_series = defaultdict(list)
    for r in rows:
        by_series[r["series"]].append(r)

    order = [k for k in SERIES if k in by_series] + [UNCLASSIFIED]
    order = [k for k in order if k in by_series]

    print("=" * 92)
    print("FACTUAL-CHECK COVERAGE ACROSS THE CORPUS".center(92))
    print(("generated %s  |  %d published posts  |  %d draft%s excluded"
           % (today, len(rows), len(drafts), "" if len(drafts) == 1 else "s"))
          .center(92))
    print("=" * 92)
    print("\nThis reports COVERAGE, not correctness. Every column below says")
    print("whether something is looking, never whether what it found was right.")

    # -- 1. corpus ---------------------------------------------------------
    body = []
    for key in order:
        rs = by_series[key]
        dates = [r["date"] for r in rs if r["date"]]
        body.append([
            key, len(rs),
            min(dates).isoformat() if dates else "-",
            max(dates).isoformat() if dates else "-",
        ])
    body.append(["TOTAL", len(rows), "", ""])
    table("1. CORPUS", ["series", "posts", "first", "latest"], body,
          ["<", ">", "<", "<"])

    # -- 2. verification depth --------------------------------------------
    body = []
    for key in order:
        rs = by_series[key]
        badged = sum(1 for r in rs if r["badged"])
        claims = sum(r["claims"] for r in rs)
        derives = sum(r["derives"] for r in rs)
        figs = sum(r["figures"] for r in rs)
        cov = sum(r["covered"] for r in rs)
        body.append([key, len(rs), "%d/%d" % (badged, len(rs)),
                     "%3.0f%%" % pct(badged, len(rs)),
                     claims, derives, figs, "%3.0f%%" % pct(cov, figs)])
    tb = sum(1 for r in rows if r["badged"])
    tf = sum(r["figures"] for r in rows)
    tc = sum(r["covered"] for r in rows)
    body.append(["TOTAL", len(rows), "%d/%d" % (tb, len(rows)),
                 "%3.0f%%" % pct(tb, len(rows)),
                 sum(r["claims"] for r in rows), sum(r["derives"] for r in rows),
                 tf, "%3.0f%%" % pct(tc, tf)])
    table("2. VERIFICATION DEPTH  (badge = a human signed a date; traced = printed "
          "figures that appear in a sourced claim)",
          ["series", "posts", "badged", "%", "claims", "derives", "figures", "traced"],
          body, ["<", ">", ">", ">", ">", ">", ">", ">"])

    # -- 3. checker reach --------------------------------------------------
    body = []
    for key in order:
        rs = by_series[key]
        scanned = sum(1 for r in rs
                      if ca.series_of(r["post"]) is not None)
        nrules = 0 if key == UNCLASSIFIED else source_rule_count(key)
        verdict = "ok"
        if scanned == 0:
            verdict = "NOT SCANNED"
        elif nrules == 0:
            verdict = "no source rules"
        elif scanned < len(rs):
            verdict = "partial"
        body.append([key, len(rs), "%d/%d" % (scanned, len(rs)),
                     nrules or "-", verdict])
    table("3. CHECKER REACH  (a clean result from a checker with no rules means "
          "nothing was tested)",
          ["series", "posts", "assertion-scanned", "source rules", "verdict"],
          body, ["<", ">", ">", ">", "<"])

    # -- 4. freshness ------------------------------------------------------
    buckets = [("under 30 days", 0, 30), ("30-90 days", 30, 90),
               ("90-180 days", 90, 180),
               ("over %d days (stale)" % STALE_DAYS, STALE_DAYS, 10 ** 6)]
    verified = [r for r in rows if r["verified"]]
    body = []
    for label, lo, hi in buckets:
        n = sum(1 for r in verified
                if lo <= (today - r["verified"]).days < hi)
        body.append([label, n, "%5.1f%%" % pct(n, len(verified)), bar(pct(n, len(verified)))])
    body.append(["no badge at all", len(rows) - len(verified),
                 "%5.1f%%" % pct(len(rows) - len(verified), len(rows)), ""])
    table("4. FRESHNESS OF VERIFICATION  (%d badged posts)" % len(verified),
          ["age of check", "posts", "share", ""], body, ["<", ">", ">", "<"])

    # -- 5. outstanding ----------------------------------------------------
    kinds = defaultdict(int)
    posts_with = set()
    for post, counts in flags.items():
        for kind, n in counts.items():
            kinds[kind] += n
            posts_with.add(post)
    body = [[k, v] for k, v in sorted(kinds.items(), key=lambda x: -x[1])]
    body.append(["posts affected", len(posts_with)])
    table("5. OUTSTANDING ADVISORY FINDINGS", ["kind", "count"], body, ["<", ">"])

    # -- 6. blind spots ----------------------------------------------------
    unscanned = [r for r in rows if ca.series_of(r["post"]) is None]
    nobadge = [r for r in rows if not r["badged"]]
    noclaims = [r for r in rows if r["badged"] and r["claims"] == 0]
    zerotraced = [r for r in rows
                  if r["badged"] and r["figures"] >= 5 and r["covered"] == 0]
    norules = [k for k in order
               if k != UNCLASSIFIED and source_rule_count(k) == 0]

    print("\n6. BLIND SPOTS -- where nothing is looking")
    print("-" * 92)
    print("  %-58s %4d posts  (%.0f%%)"
          % ("never scanned by check_assertions (no series prefix)",
             len(unscanned), pct(len(unscanned), len(rows))))
    print("  %-58s %4d posts  (%.0f%%)"
          % ("carry no verification badge", len(nobadge),
             pct(len(nobadge), len(rows))))
    print("  %-58s %4d posts" % ("badged but with zero claims", len(noclaims)))
    print("  %-58s %4d posts"
          % ("badged, 5+ printed figures, none traced to a claim",
             len(zerotraced)))
    print("  %-58s %4d series %s"
          % ("series with no check_sources topic rule", len(norules),
             "(" + ", ".join(norules) + ")" if norules else ""))

    # Verified-after-published is a retro-check, and retro-checks are honest:
    # the badge says a human confirmed the figures on that date, and they did.
    # arch-001..014 all carry verified: 2026-09-06, one sweep across posts that
    # went out before the badge existed. Reported so the count is visible, NOT
    # as a fault -- calling 27 legitimate back-fills dishonest is how a report
    # gets ignored, which is the same standard the rules themselves are held to.
    future = [r for r in rows if r["date"] and r["date"] > today]
    retro = [r for r in rows if r["verified"] and r["date"]
             and r["verified"] > r["date"]]
    sweeps = defaultdict(int)
    for r in retro:
        sweeps[r["verified"]] += 1
    biggest = max(sweeps.items(), key=lambda kv: kv[1]) if sweeps else None
    print("  %-58s %4d posts" % ("dated ahead of today (normal for a held post)",
                                 len(future)))
    print("  %-58s %4d posts%s"
          % ("retro-verified after publication (legitimate back-fill)",
             len(retro),
             "  largest sweep %s: %d" % (biggest[0], biggest[1]) if biggest else ""))
    print("-" * 92)
    print("  None of the above is evidence a post is wrong. Each is a place a")
    print("  wrong post would not be noticed.")

    if zerotraced:
        print("\n  Badged with untraced figures -- the badge claims more than the")
        print("  claim list supports:")
        for r in sorted(zerotraced, key=lambda r: -r["figures"])[:12]:
            print("    %-52s %3d figures, 0 traced" % (r["post"][:52], r["figures"]))

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
