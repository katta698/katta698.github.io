#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the complete announcement inventory for a Weekly Intelligence post.

Emits the HTML for the "Complete inventory" section — every AWS What's New
announcement in the date range, grouped by day, each linked — and validates
every URL before writing it.

Both halves matter. The inventory comes straight from the raw RSS (see
fetch_week.py for why that is not negotiable), so nothing is dropped. The
validation pass then confirms each link actually resolves, because a reference
list a reader cannot follow is worse than no reference list: it looks
authoritative and is not.

Usage
-----
    python scripts/build_weekly_inventory.py 2026-08-03 2026-08-09 > section.html

Exits non-zero if any link fails, so a broken reference cannot ship silently.
"""
import concurrent.futures
import datetime
import html
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from fetch_week import fetch, parse  # noqa: E402


def gists(raw):
    """Map link -> AWS's own one-line summary, from the feed's description.

    Using AWS's wording rather than paraphrasing keeps the inventory honest at
    this scale: 66 hand-written summaries a week is where errors would creep in,
    and the reader can check any of them against the linked source.
    """
    out = {}
    for it in ET.fromstring(raw).findall(".//item"):
        link = (it.findtext("link") or "").strip()
        desc = html.unescape(it.findtext("description") or "")
        text = re.sub(r"<[^>]+>", " ", desc)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        # Prefer the first sentence; fall back to a clean truncation.
        m = re.match(r"(.{40,240}?[.!?])(\s|$)", text)
        summary = m.group(1) if m else (
            text[:200].rsplit(" ", 1)[0] + "…" if len(text) > 200 else text)
        out[link] = summary
    return out

# Announcements that already have a full write-up, matched on a distinctive
# fragment of the announcement URL.
COVERED = {
    "aws-Lambda-provisioned-sqs-esm-max-pollers":
        "/blog/aws-daily-intelligence-lambda-sqs-provisioned-mode-pollers/",
    "aws-application-network":
        "/blog/aws-daily-intelligence-elb-rfc9151-cnsa-tls-policies/",
    "amazon-dynamodb-vector-search":
        "/blog/aws-daily-intelligence-dynamodb-vector-search/",
    "amazon-ecs-fractional-gpu":
        "/blog/aws-daily-intelligence-ecs-fractional-gpu-scheduling/",
    "amazon-vpc-ipam-bgp-rpki-byoip":
        "/blog/aws-daily-intelligence-ipam-bgp-route-protection/",
}


def check(url):
    """Return (url, status). AWS rejects HEAD on some pages, so fall back."""
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url, method=method, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return url, r.status
        except urllib.error.HTTPError as e:
            if method == "GET":
                return url, e.code
        except Exception as e:  # network, timeout, DNS
            if method == "GET":
                return url, "ERR %s" % type(e).__name__
    return url, "ERR"


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    start = datetime.date.fromisoformat(sys.argv[1])
    end = datetime.date.fromisoformat(sys.argv[2])

    raw = fetch()
    rows = [r for r in parse(raw) if start <= r[0] <= end]
    if not rows:
        print("No announcements in range.", file=sys.stderr)
        return 1
    summaries = gists(raw)

    urls = sorted({l for _, _, l in rows})
    print("Validating %d links..." % len(urls), file=sys.stderr)
    bad = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for url, status in ex.map(check, urls):
            if status != 200:
                bad.append((url, status))

    by = {}
    for d, t, l in rows:
        by.setdefault(d, []).append((t, l))

    out = []
    for d in sorted(by, reverse=True):
        items = by[d]
        out.append("    <h3>%s &mdash; %d announcements</h3>"
                   % (d.strftime("%A %d %B"), len(items)))
        out.append("    <ul>")
        for t, l in items:
            mark = ""
            for frag, post in COVERED.items():
                if frag in l:
                    # On its own line after the summary. Inline, it butts up
                    # against the title and reads as part of it.
                    mark = ('<span class="inv-gist"><a href="%s">'
                            "Full write-up &rarr;</a></span>" % post)
            gist = summaries.get(l, "")
            # No inline style: clean_html() strips the style attribute from
            # every tag, so the muted colour must come from a theme class.
            out.append(
                '      <li><a href="%s"><strong>%s</strong></a>'
                '<span class="inv-gist">%s</span>%s</li>'
                % (html.escape(l, quote=True), html.escape(t),
                   html.escape(gist), mark))
        out.append("    </ul>")

    sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))

    print("\n%d announcements, %d unique links" % (len(rows), len(urls)),
          file=sys.stderr)
    if bad:
        print("BROKEN LINKS (%d):" % len(bad), file=sys.stderr)
        for url, status in bad:
            print("  %s  %s" % (status, url), file=sys.stderr)
        return 1
    print("all links return 200", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
