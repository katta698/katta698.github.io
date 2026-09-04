#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ask the announcement store what changed.

    python scripts/news.py S3
    python scripts/news.py EC2 --days 7
    python scripts/news.py "org policy" --cloud gcp --days 90
    python scripts/news.py --cloud azure --days 7          # everything, one week
    python scripts/news.py Aurora --all                    # include blogs + CVEs

Deliberately a filter, not a search engine. A service tag and a date range are
facts about a record; "relevance" is not. That distinction is the whole reason
this exists separately from the blog's Ask widget -- semantic similarity has no
notion of when a thing happened or which service it was about, which is exactly
how "Todays GCP Arch post" came back as three roundups from August.

Matching, in order:

  1. the `services` tags, which news_tag.py filled from the vendor's own naming
  2. the GCP `product` field
  3. the headline text, as a fallback

A tag hit and a text hit are reported differently, because they are not the same
claim. "S3" tagged is an S3 announcement; "S3" in the text might be a customer
story that mentions it once -- the case that made plain text search unusable.
"""
import argparse
import datetime
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import news_store as store            # noqa: E402

# What a reader means by "what's new" is an announcement. Blogs and CVEs are
# available but opt-in: including them by default is what buried the Azure
# answers under 4,353 MSRC notices.
DEFAULT_CLASSES = ("announcement", "release")


def load(clouds):
    rows = []
    for cloud in clouds:
        for ym in store.all_months(cloud):
            rows.extend(store.load_month(cloud, ym).values())
    return rows


# Hyphens count as word boundaries, not as word characters.
#
# The boundary was (?<![\w-]) ... (?![\w-]), which refused to match a term that
# had a hyphen either side of it -- so searching "SSM" could not find
# "amazon-ssm-agent", and the AWS Systems Manager CVE that became Daily
# Intelligence #21 was unfindable while sitting in the store. Vendors name
# things this way constantly: amazon-ssm-agent, aws-cli, cos-gpu-installer.
#
# The exclusion existed to stop a match inside a word, and \w alone still does
# that: "ssm" will not match "ssmith", but it will match "amazon-ssm-agent".


def _word_regexes(needle, prefix):
    """One regex per word of the query, exact or prefix-matching.

    "org policy" found nothing while "organization policy" sat in the store,
    because an exact match cannot know "org" is how a person abbreviates it --
    so prefix matching has to exist. But it cannot be the default: "SSM Agent"
    reached "GitHub Copilot in SQL Server Management Studio (SSMS)", because
    SSMS really does begin with SSM. So callers ask for one or the other, and
    the exact pass runs first.
    """
    out = []
    for w in re.findall(r"[\w-]+", needle):
        if prefix and len(w) >= 3:
            out.append(re.compile(r"(?<!\w)%s\w*" % re.escape(w), re.I))
        else:
            out.append(re.compile(r"(?<!\w)%s(?!\w)" % re.escape(w), re.I))
    return out


def match(record, needle):
    """(matched, how). 'tag' is a service tag, 'text' only the prose.

    The two are reported separately because they are not the same claim: a
    tagged S3 record IS an S3 announcement, while a text hit might be a customer
    story that mentions it once.
    """
    if not needle:
        return True, "all"
    exact = re.compile(r"(?<!\w)%s(?!\w)" % re.escape(needle), re.I)
    for s in record.get("services") or []:
        if exact.search(s) or needle.lower() in s.lower():
            return True, "tag"
    product = record.get("product") or ""
    if product and needle.lower() in product.lower():
        return True, "tag"

    hay = "%s %s" % (record.get("headline", ""), record.get("summary", ""))
    if exact.search(hay):
        return True, "text"

    # All words present, each matched EXACTLY. This is tried before any prefix
    # matching, because prefixes are where short acronyms go wrong: "SSM Agent"
    # matched "Agent mode for GitHub Copilot in SQL Server Management Studio
    # (SSMS)" -- SSMS legitimately starts with SSM. Exact-first means a real hit
    # is never displaced by a looser one.
    words = _word_regexes(needle, prefix=False)
    if len(words) > 1 and all(w.search(hay) for w in words):
        return True, "text"
    return False, None


def match_loose(record, needle):
    """Prefix matching, used only when exact matching found nothing at all.

    "org policy" has to be able to reach "organization policy", and no exact
    rule does that. Running it as a fallback rather than as the default keeps
    the SSM/SSMS collision out of results that had a better answer available.
    """
    if not needle:
        return False
    hay = "%s %s %s" % (record.get("headline", ""), record.get("summary", ""),
                        " ".join(record.get("services") or []))
    words = _word_regexes(needle, prefix=True)
    return bool(words) and all(w.search(hay) for w in words)


def main():
    ap = argparse.ArgumentParser(
        description="Ask the announcement store what changed.")
    ap.add_argument("query", nargs="?", default="",
                    help="service or phrase, e.g. S3, EC2, 'org policy'")
    ap.add_argument("--cloud", choices=store.CLOUDS, action="append")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--since", help="YYYY-MM-DD, overrides --days")
    ap.add_argument("--all", action="store_true",
                    help="include blog posts and security bulletins")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    clouds = tuple(args.cloud) if args.cloud else store.CLOUDS
    start = (args.since if args.since else
             (datetime.date.today()
              - datetime.timedelta(days=args.days)).isoformat())

    rows = load(clouds)
    if not rows:
        print("  store is empty -- run: python scripts/news_store.py ingest")
        return 1

    # Report coverage honestly. A question about March answered from a store
    # that starts in August must say so rather than return a confident nothing.
    earliest = min(r["date"] for r in rows)

    in_window = [r for r in rows if r["date"] >= start]
    publishable = [r for r in in_window
                   if args.all or r.get("class") in DEFAULT_CLASSES]

    hits = [(how, r) for how, r in
            ((match(r, args.query)[1], r) for r in publishable)
            if how]

    # Order matters, and getting it wrong is worse than having no fallback.
    # An EXACT hit hidden by the class filter beats a prefix hit inside it:
    # searching "SSM Agent" answered with "GitHub Copilot in SQL Server
    # Management Studio (SSMS)" -- a prefix match on SSMS -- while five genuine
    # SSM records sat one filter away, classed as blog and security. The junk
    # result crowded out the useful signpost.
    elsewhere, older, loose = [], [], False

    if not hits and args.query and not args.all:
        elsewhere = [r for r in in_window
                     if r.get("class") not in DEFAULT_CLASSES
                     and match(r, args.query)[0]]

    if not hits and not elsewhere and args.query:
        older = [r for r in rows
                 if r["date"] < start and match(r, args.query)[0]
                 and (args.all or r.get("class") in DEFAULT_CLASSES)]

    # Only once nothing exact exists anywhere is a prefix match worth showing.
    if not hits and not elsewhere and not older and args.query:
        hits = [("text", r) for r in publishable if match_loose(r, args.query)]
        loose = bool(hits)

    hits.sort(key=lambda x: x[1]["date"], reverse=True)

    if args.json:
        print(json.dumps([h[1] for h in hits[:args.limit]],
                         indent=2, ensure_ascii=False))
        return 0

    label = args.query or "everything"
    print("\n  %s  -- %s, since %s%s"
          % (label, "/".join(clouds), start,
             "" if args.all else "  (announcements only)"))
    if not hits:
        print("\n  nothing found under this filter.")
        if elsewhere:
            kinds = sorted(set(r.get("class", "?") for r in elsewhere))
            print("  BUT %d match(es) exist as %s. Add --all to see them:"
                  % (len(elsewhere), " and ".join(kinds)))
            for r in sorted(elsewhere, key=lambda r: r["date"],
                            reverse=True)[:5]:
                print("      %s  %-5s [%-12s] %s"
                      % (r["date"], r["cloud"], r.get("class", "?"),
                         r["headline"][:52]))
        if older:
            print("  BUT %d match(es) are older than %s. Widen with --days:"
                  % (len(older), start))
            for r in sorted(older, key=lambda r: r["date"], reverse=True)[:5]:
                print("      %s  %-5s %s"
                      % (r["date"], r["cloud"], r["headline"][:60]))
    else:
        if loose:
            print("  (no exact match; these are loose/prefix matches)")
        if args.query:
            by_tag = sum(1 for h in hits if h[0] == "tag")
            print("  %d result(s), %d by service tag, %d by text only\n"
                  % (len(hits), by_tag, len(hits) - by_tag))
        else:
            # With no query nothing was matched at all, so a tag/text split
            # would be reporting on a comparison that never happened.
            print("  %d result(s)\n" % len(hits))
        for how, r in hits[:args.limit]:
            flag = " " if how in ("tag", "all") else "~"
            svc = ", ".join(r.get("services") or []) or "-"
            print("  %s %s  %-5s  %-58s"
                  % (flag, r["date"], r["cloud"], r["headline"][:58]))
            print("      %-28s %s" % (svc[:28], r["url"][:76]))
    if start < earliest:
        print("\n  NOTE: the store starts at %s; anything before that was never"
              " captured." % earliest)
    print("  ~ = matched on text only, not a service tag.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
