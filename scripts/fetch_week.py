#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull a complete, deterministic inventory of AWS What's New announcements.

Why this exists
---------------
The AWS Weekly Intelligence post promises a reader that they do not need to
check anywhere else. That promise only holds if the inventory behind it is
complete, and it was not.

Announcements were previously gathered by asking a model to read the What's New
feed and list what it found. Model summarisation silently drops items: for the
week of 3-7 August 2026 that method captured 42 of 66 announcements. A third of
the week was missing, with no error and no way to notice.

This script parses the raw RSS instead. No summarisation, no judgement, no
omissions — every <item> in the feed, with its real publication date and link.

Usage
-----
    python scripts/fetch_week.py                     # the last 7 days
    python scripts/fetch_week.py 2026-08-03 2026-08-09
    python scripts/fetch_week.py --markdown          # ready to paste into a post

Limits worth knowing
--------------------
The feed is a rolling window of roughly 100 items, which at current volume is
about two weeks. Anything older than that cannot be recovered from this source,
so run it weekly rather than trying to reconstruct history later. The feed is
also the only source here: it does not carry AWS blog posts, event and
conference news, or documentation changes, which still need gathering by hand.
"""
import argparse
import collections
import datetime
import email.utils
import io
import sys
import urllib.request
import xml.etree.ElementTree as ET

FEED = "https://aws.amazon.com/about-aws/whats-new/recent/feed/"

# Second source. The What's New feed does not carry News Blog posts, and the
# first roundup missed all three of that week's because only one feed was being
# read. Anything with a feed gets parsed; anything without one has to be a named
# manual step rather than an assumption that it was covered.
BLOG_FEED = "https://aws.amazon.com/blogs/aws/feed/"

# No feed exists for these. They are listed so the gap is visible rather than
# silently absent, and must be checked by hand before publishing a roundup:
#   - Events, summits and re:Invent news   https://aws.amazon.com/events/
#   - Security bulletins                   https://aws.amazon.com/security/security-bulletins/
MANUAL_SOURCES = ("events", "security bulletins")


def fetch(url=FEED):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def parse(raw):
    """Return [(date, title, link)] sorted newest first."""
    items = ET.fromstring(raw).findall(".//item")
    out = []
    for it in items:
        pub = it.findtext("pubDate")
        if not pub:
            continue
        d = email.utils.parsedate_to_datetime(pub).date()
        out.append((d, (it.findtext("title") or "").strip(),
                    (it.findtext("link") or "").strip()))
    return sorted(out, key=lambda r: r[0], reverse=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start", nargs="?", help="YYYY-MM-DD (default: 7 days ago)")
    ap.add_argument("end", nargs="?", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--markdown", action="store_true",
                    help="emit a markdown table per day")
    args = ap.parse_args()

    today = datetime.date.today()
    end = datetime.date.fromisoformat(args.end) if args.end else today
    start = (datetime.date.fromisoformat(args.start) if args.start
             else end - datetime.timedelta(days=6))

    rows = [r for r in parse(fetch()) if start <= r[0] <= end]
    blog = [r for r in parse(fetch(BLOG_FEED)) if start <= r[0] <= end]

    # Report every source explicitly. A source returning nothing must look
    # different from a source that was never consulted — that ambiguity is how
    # the News Blog went unnoticed in the first roundup.
    print("What's New feed : %d announcements" % len(rows), file=sys.stderr)
    print("AWS News Blog   : %d posts" % len(blog), file=sys.stderr)
    for name in MANUAL_SOURCES:
        print("%-16s: NO FEED — check by hand" % name, file=sys.stderr)
    print(file=sys.stderr)

    if not rows:
        print("No announcements in range. The feed is a rolling ~100-item "
              "window; anything older has aged out.", file=sys.stderr)
        return 1

    by_day = collections.OrderedDict()
    for d, t, l in rows:
        by_day.setdefault(d, []).append((t, l))

    out = io.StringIO()
    if args.markdown:
        for d in sorted(by_day, reverse=True):
            out.write("\n### %s (%d)\n\n" % (d.strftime("%A %-d %B %Y")
                                             if sys.platform != "win32"
                                             else d.strftime("%A %d %B %Y"),
                                             len(by_day[d])))
            for t, l in by_day[d]:
                out.write("- [%s](%s)\n" % (t, l))
    else:
        out.write("%s to %s — %d announcements\n\n" % (start, end, len(rows)))
        for d in sorted(by_day, reverse=True):
            out.write("%s  (%d)\n" % (d, len(by_day[d])))
            for t, l in by_day[d]:
                out.write("   %s\n      %s\n" % (t, l))
            out.write("\n")
        if blog:
            out.write("AWS News Blog (%d)\n" % len(blog))
            for d, t, l in blog:
                out.write("   %s  %s\n      %s\n" % (d, t, l))

    sys.stdout.buffer.write(out.getvalue().encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
