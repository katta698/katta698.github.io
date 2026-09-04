#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check the store against things we KNOW were announced.

    python scripts/audit_news_coverage.py

WHY
---
Every gap found so far was found by accident: somebody remembered a specific
announcement, searched for it, and got nothing. That works only for news you
already know about, which is the smaller half of the problem -- and it is a
terrible way to discover that a whole month is missing.

There is ground truth in this repo. DAILY-BACKLOG.md records every AWS item
ranked in a daily run, with its official link, whether or not it became a post.
The published weekly inventories are complete, link-checked lists for their
weeks. Both were compiled independently of the store, so measuring the store
against them says how much it is missing WITHOUT anyone having to remember
anything.

An item that is in the backlog and not in the store is a hole. An item in
neither is invisible to both, and no amount of checking here will find it --
which is a limit worth stating rather than papering over.

Matched on URL, not on words: a headline can be reworded between the feed and
the backlog, but the link is the announcement's identity.
"""
import io
import os
import re
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import news_store as store          # noqa: E402

BACKLOG = os.path.join(ROOT, "DAILY-BACKLOG.md")
POSTS = os.path.join(ROOT, "posts")

# Trailing slashes, query strings and anchors differ between how a link is
# written by hand and how a feed serves it; neither changes which announcement
# it is.
def norm(url):
    u = (url or "").strip().lower()
    u = re.sub(r"[#?].*$", "", u)
    u = re.sub(r"/+$", "", u)
    u = re.sub(r"^https?://", "", u)
    return u


def store_urls():
    out = {}
    for cloud in store.CLOUDS:
        for ym in store.all_months(cloud):
            for r in store.load_month(cloud, ym).values():
                n = norm(r.get("url"))
                if n:
                    out.setdefault(n, r)
    return out


LINK_RE = re.compile(r"\[link\]\((https?://[^)]+)\)")
ROW_RE = re.compile(r"^\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|\s*\[link\]\((https?://[^)]+)\)",
                    re.M)


def backlog_items():
    """(headline, url) for every ranked item in DAILY-BACKLOG.md."""
    if not os.path.isfile(BACKLOG):
        return []
    text = io.open(BACKLOG, encoding="utf-8").read()
    out = []
    for m in ROW_RE.finditer(text):
        title = m.group(1).strip().strip("*` ")
        out.append((title, m.group(5)))
    return out


def inventory_items():
    """(headline, url) from the published weekly inventories."""
    out = []
    if not os.path.isdir(POSTS):
        return out
    for name in sorted(os.listdir(POSTS)):
        if not re.match(r"^(weekly|azw|gcpweekly)-\d+", name):
            continue
        html = io.open(os.path.join(POSTS, name), encoding="utf-8").read()
        for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
                             html, re.S):
            url, label = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
            if any(h in url for h in ("aws.amazon.com/about-aws/whats-new",
                                      "azure.microsoft.com/updates",
                                      "cloud.google.com/release-notes",
                                      "docs.cloud.google.com/release-notes")):
                out.append((label.strip()[:90], url))
    return out


def report(name, items, have):
    if not items:
        print("  %s: no items found to check against" % name)
        return 0, 0
    seen, missing = set(), []
    for title, url in items:
        n = norm(url)
        if n in seen:
            continue
        seen.add(n)
        if n not in have:
            missing.append((title, url))
    found = len(seen) - len(missing)
    pct = 100.0 * found / len(seen) if seen else 0
    print("\n  %s" % name)
    print("    %d distinct link(s); %d in the store, %d MISSING (%.0f%% covered)"
          % (len(seen), found, len(missing), pct))
    if missing:
        by_year = collections.Counter(
            re.search(r"/(20\d\d)/", u).group(1) if re.search(r"/(20\d\d)/", u)
            else "?" for _, u in missing)
        print("    missing by year: %s"
              % ", ".join("%s=%d" % kv for kv in sorted(by_year.items())))
        for title, url in missing[:8]:
            print("      - %-62s" % title[:62])
            print("        %s" % url[:100])
        if len(missing) > 8:
            print("      ... and %d more" % (len(missing) - 8))
    return found, len(missing)


def main():
    have = store_urls()
    print("  store holds %d distinct URLs" % len(have))

    total_missing = 0
    for name, items in (("DAILY-BACKLOG.md (AWS items ranked in a daily run)",
                         backlog_items()),
                        ("Published weekly inventories", inventory_items())):
        _f, m = report(name, items, have)
        total_missing += m

    print("\n  %d known announcement(s) the store cannot answer for." % total_missing)
    print("  Anything absent from BOTH the store and these sources is invisible")
    print("  to this audit -- it can measure known gaps, not unknown ones.")
    # Reporting only. This is a measurement of history that was already lost
    # before the store existed; failing a publish over it would block every
    # publish forever, and fixing it means backfilling, not editing code.
    return 0


if __name__ == "__main__":
    sys.exit(main())
