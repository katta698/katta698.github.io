#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull a complete, deterministic inventory of what Google Cloud published in a date range.

Why this exists
---------------
Same reason as `fetch_week.py` does for AWS: the Weekly Intelligence post
promises a reader they do not need to look anywhere else, and that promise rests
entirely on the source list being right. A reader cannot check it, and nothing
errors when it is wrong. The AWS series failed that twice — once by asking a
model to summarise a feed (24 of 66 announcements silently dropped), once by
reading two sources when a dozen existed (~170 unread posts).

Google Cloud is not shaped like AWS, and the differences below were measured on
14 August 2026, not assumed.

**The combined release-notes feed is day-granular, not item-granular.** One
Atom <entry> is one *calendar day*, and its <content> is an HTML blob holding
every product's notes for that day — up to 447 notes in a single entry. Counting
entries counts days, not announcements. Parsing means exploding that HTML on
`<h2 class="release-note-product-title">` for the product and `<h3>` for each
note under it.

**The combined feed is complete, not curated.** This was the open question in
INTELLIGENCE-SERIES-BRIEF.md, and the answer inverts what the brief expected.
Cross-checked on 14 August 2026: for eight products with live per-product feeds
(Cloud SQL, Apigee, GKE, Cloud Run, Bigtable, Spanner, BigQuery and IAM), every
dated note in the per-product feed also appears in the combined feed for the
same day. Zero misses.

**The per-product feeds are the unreliable ones.** They are NOT the source list,
and using them as one would make the inventory worse. Measured the same day:
compute-engine's feed is frozen at April 2020 — 2,307 days stale — while the
combined feed carries Compute Engine notes throughout. anthos stopped in 2022.
Roughly a third of the rest run months behind. `--audit --products` prints that
table, because a stale feed returns HTTP 200 and looks healthy.

**The cap is 30 entries on every feed**, which for the combined feed means 30
*days* rather than 30 items — about a month of slack, where the AWS What's New
feed gives 12 days. Comfortable for a weekly cadence, but measured, not assumed,
and re-measured by `--audit` on every run.

Usage
-----
    python scripts/fetch_week_gcp.py                    # the last 7 days
    python scripts/fetch_week_gcp.py 2026-08-10 2026-08-14
    python scripts/fetch_week_gcp.py --markdown         # ready to paste into a post
    python scripts/fetch_week_gcp.py --audit            # probe every feed, print health
    python scripts/fetch_week_gcp.py --audit --products # also probe per-product feeds
"""
import argparse
import collections
import concurrent.futures
import datetime
import email.utils
import io
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

ATOM = "{http://www.w3.org/2005/Atom}"

# docs.cloud.google.com, not cloud.google.com. The documentation moved: requests
# to cloud.google.com/feeds/* answer 301 to docs.cloud.google.com. Following a
# redirect on every fetch works but doubles the request count, and the GKE feeds
# land somewhere else again (/static/feeds/gke-*), which a naive rewrite of the
# hostname would not find.
COMBINED = "https://docs.cloud.google.com/feeds/gcp-release-notes.xml"

# Every Google Cloud source with a machine-readable feed. Adding a source here is
# the only way it gets read; there is no discovery. Re-probe with --audit when a
# roundup feels thin.
#
# kind drives the parser, because these four feeds have four different shapes:
#   daynotes — Atom, one entry per calendar day, many notes inside the content
#   bulletin — Atom, one entry per bulletin, real date is "Published:" in content
#   gkebull  — Atom, one entry per bulletin, entry <updated> is per-item and real
#   rss      — ordinary RSS with per-item pubDate
SOURCES = [
    ("Release Notes",     COMBINED, "daynotes"),
    ("Security Bulletins",
     "https://docs.cloud.google.com/feeds/google-cloud-security-bulletins.xml", "bulletin"),
    ("GKE Sec Bulletins",
     "https://docs.cloud.google.com/static/feeds/gke-security-bulletins.xml", "gkebull"),
    ("Cloud Blog",        "https://cloudblog.withgoogle.com/rss/", "rss"),
]

# Probed only by --audit --products, never used to build an inventory. They exist
# to answer "has the combined feed gone quiet, or has this product?" and to keep
# the measured evidence for that decision reproducible rather than a claim in a
# comment. A 404 here means the slug guess is wrong, not that the product has no
# release notes -- the combined feed carries all of them regardless.
PRODUCT_SLUGS = [
    "compute-engine", "bigquery", "kubernetes-engine", "cloud-run", "cloud-storage",
    "cloud-sql", "spanner", "bigtable", "dataflow", "dataproc", "pubsub", "vertex-ai",
    "iam", "cloud-functions", "vpc", "cloud-load-balancing", "cloud-dns", "cloud-kms",
    "secret-manager", "cloud-build", "monitoring", "logging", "apigee", "alloydb",
    "memorystore", "filestore", "composer", "dataplex", "looker", "anthos",
    "workflows", "eventarc", "batch", "cloud-cdn", "cloud-armor", "cloud-vpn",
    "cloud-interconnect", "resource-manager", "datastream",
]

# Genuinely no feed, and therefore a manual step printed on every run so the gap
# stays visible rather than silently absent:
#   - Google Cloud Next and event announcements   https://cloud.google.com/events
MANUAL_SOURCES = ("Next / events",)

TAG_RE = re.compile(r"<[^>]+>")
PRODUCT_SPLIT_RE = re.compile(r'<h2 class="release-note-product-title">(.*?)</h2>', re.S)
NOTE_RE = re.compile(r"<h3[^>]*>(.*?)</h3>(.*?)(?=<h3[^>]*>|$)", re.S)
PUBLISHED_RE = re.compile(r"Published:\s*</strong>\s*(\d{4}-\d\d-\d\d)")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def text_of(html, limit=160):
    """Flatten an HTML fragment to a one-line summary."""
    s = TAG_RE.sub(" ", html or "")
    s = (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
          .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " "))
    s = " ".join(s.split())
    return s[:limit].rstrip() + ("…" if len(s) > limit else "")


def _entries(raw):
    return ET.fromstring(raw).findall(".//" + ATOM + "entry")


def parse_daynotes(raw):
    """Explode the combined feed: one entry per day, many notes inside it.

    Returns [(date, product, kind, summary, link)]. The day is taken from the
    entry, not from anything inside the content, because the content carries no
    per-note date -- the day *is* the entry.
    """
    out = []
    for e in _entries(raw):
        day = datetime.date.fromisoformat((e.findtext(ATOM + "updated") or "")[:10])
        link_el = e.find(ATOM + "link")
        link = link_el.get("href") if link_el is not None else ""
        content = (e.find(ATOM + "content").text or "") if e.find(ATOM + "content") is not None else ""
        # Split into per-product blocks. re.split keeps the captured product
        # name, so chunks alternate [preamble, name, body, name, body, ...].
        chunks = PRODUCT_SPLIT_RE.split(content)
        for i in range(1, len(chunks), 2):
            product = text_of(chunks[i], 80)
            body = chunks[i + 1] if i + 1 < len(chunks) else ""
            notes = NOTE_RE.findall(body)
            if not notes:
                out.append((day, product, "Note", text_of(body), link))
                continue
            for kind, note_body in notes:
                out.append((day, product, text_of(kind, 30), text_of(note_body), link))
    return sorted(out, key=lambda r: r[0], reverse=True)


def parse_bulletin(raw):
    """Security bulletins. Every entry shares one <updated> — the time the feed
    was generated — so the real date has to come from "Published:" in the body.
    Trusting <updated> here would date the whole backlog to today."""
    out = []
    for e in _entries(raw):
        content = (e.find(ATOM + "content").text or "") if e.find(ATOM + "content") is not None else ""
        m = PUBLISHED_RE.search(content)
        if not m:
            continue
        link_el = e.find(ATOM + "link")
        out.append((datetime.date.fromisoformat(m.group(1)),
                    "Security bulletin",
                    e.findtext(ATOM + "title") or "",
                    text_of(content),
                    link_el.get("href") if link_el is not None else ""))
    return sorted(out, key=lambda r: r[0], reverse=True)


def parse_gkebull(raw):
    """GKE bulletins: <updated> is genuinely per-entry here, unlike the feed above."""
    out = []
    for e in _entries(raw):
        content = (e.find(ATOM + "content").text or "") if e.find(ATOM + "content") is not None else ""
        m = PUBLISHED_RE.search(content)
        day = (datetime.date.fromisoformat(m.group(1)) if m
               else datetime.date.fromisoformat((e.findtext(ATOM + "updated") or "")[:10]))
        link_el = e.find(ATOM + "link")
        out.append((day, "GKE security bulletin", e.findtext(ATOM + "title") or "",
                    text_of(content), link_el.get("href") if link_el is not None else ""))
    return sorted(out, key=lambda r: r[0], reverse=True)


def parse_rss(raw):
    out = []
    for it in ET.fromstring(raw).findall(".//item"):
        pub = it.findtext("pubDate")
        if not pub:
            continue
        out.append((email.utils.parsedate_to_datetime(pub).date(),
                    "Blog", "Post",
                    (it.findtext("title") or "").strip(),
                    (it.findtext("link") or "").strip()))
    return sorted(out, key=lambda r: r[0], reverse=True)


PARSERS = {"daynotes": parse_daynotes, "bulletin": parse_bulletin,
           "gkebull": parse_gkebull, "rss": parse_rss}


def load(source):
    """Fetch and parse one source. Never raises — a dead feed must be reported,
    not crash the run, and must never look like an empty one either."""
    name, url, kind = source
    try:
        return name, kind, PARSERS[kind](fetch(url)), None
    except Exception as exc:                                  # noqa: BLE001
        return name, kind, [], "%s: %s" % (type(exc).__name__, exc)


def gather():
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(load, SOURCES))


def probe_product(slug):
    url = "https://docs.cloud.google.com/feeds/%s-release-notes.xml" % slug
    try:
        es = _entries(fetch(url))
        days = sorted(datetime.date.fromisoformat((e.findtext(ATOM + "updated") or "")[:10])
                      for e in es)
        return slug, len(es), days[0], days[-1], None
    except Exception as exc:                                  # noqa: BLE001
        return slug, 0, None, None, getattr(exc, "code", type(exc).__name__)


def audit(results, with_products):
    today = datetime.date.today()
    print("%-20s %-9s %7s  %s" % ("SOURCE", "KIND", "ITEMS", "COVERAGE"))
    print("-" * 78)
    for name, kind, rows, err in results:
        if err:
            print("%-20s %-9s %7s  BROKEN — %s" % (name, kind, "-", err))
        elif not rows:
            print("%-20s %-9s %7d  EMPTY — a feed that returns nothing is broken,"
                  " not quiet" % (name, kind, 0))
        else:
            days = sorted({r[0] for r in rows})
            print("%-20s %-9s %7d  %s to %s  (%d distinct days, %d stale)"
                  % (name, kind, len(rows), days[0], days[-1],
                     len(days), (today - days[-1]).days))
    for name in MANUAL_SOURCES:
        print("%-20s %-9s %7s  no feed exists — check by hand" % (name, "-", "-"))

    # Truncation window, measured on this run rather than recalled from a comment.
    combined = next((r for n, k, r, e in results if k == "daynotes" and not e), [])
    print()
    if combined:
        days = sorted({r[0] for r in combined})
        print("TRUNCATION WINDOW (measured just now)")
        print("  Release Notes holds %d notes across %d day-entries, %s to %s."
              % (len(combined), len(days), days[0], days[-1]))
        print("  That is a %d-day window. Anything older cannot be recovered from"
              " this source." % ((days[-1] - days[0]).days + 1))
        print("  The cap is on ENTRIES (30), and one entry is one day — so the"
              " window is days, not items.")
    else:
        print("TRUNCATION WINDOW: unmeasurable — the combined feed did not parse.")

    if with_products:
        print("\nPER-PRODUCT FEED HEALTH — evidence, not a source list")
        print("These are NOT read when building an inventory. A stale feed answers")
        print("HTTP 200 and looks healthy, which is why this table exists.")
        print("\n%-24s %6s  %-12s %-12s %s" % ("PRODUCT FEED", "ITEMS", "OLDEST", "NEWEST", "STALE"))
        print("-" * 78)
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            rows = list(pool.map(probe_product, PRODUCT_SLUGS))
        dead = 0
        for slug, n, lo, hi, err in sorted(rows, key=lambda r: (r[4] is not None, r[3] or datetime.date.min)):
            if err is not None:
                print("%-24s %6s  no feed at this slug (%s)" % (slug, "-", err))
                continue
            stale = (today - hi).days
            if stale > 60:
                dead += 1
            print("%-24s %6d  %-12s %-12s %d days%s"
                  % (slug, n, lo, hi, stale, "   <-- STALE" if stale > 60 else ""))
        print("\n  %d of %d probed feeds are more than 60 days stale." % (dead, len(rows)))

    return 1 if any(e for _, _, _, e in results) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start", nargs="?", help="YYYY-MM-DD (default: 7 days ago)")
    ap.add_argument("end", nargs="?", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--markdown", action="store_true", help="emit a markdown table")
    ap.add_argument("--audit", action="store_true",
                    help="probe every feed and report its health, then exit")
    ap.add_argument("--products", action="store_true",
                    help="with --audit, also probe the per-product feeds")
    ap.add_argument("--week", action="store_true",
                    help="the Monday-Friday window this Saturday's post covers")
    args = ap.parse_args()

    results = gather()
    if args.audit:
        return audit(results, args.products)

    today = datetime.date.today()
    if args.week:
        # The post publishes Saturday and covers the Monday to Friday before it.
        # Computed rather than typed: the roundup is titled with the window, and
        # a hand-typed range is how a post ends up claiming days it did not cover.
        # Run on any day, it resolves to the most recent completed Mon-Fri.
        saturday = today - datetime.timedelta(days=(today.weekday() - 5) % 7)
        start, end = saturday - datetime.timedelta(days=5), saturday - datetime.timedelta(days=1)
        print("Week window: %s to %s (for the Saturday %s post)"
              % (start, end, saturday), file=sys.stderr)
    else:
        end = datetime.date.fromisoformat(args.end) if args.end else today
        start = (datetime.date.fromisoformat(args.start) if args.start
                 else end - datetime.timedelta(days=6))

    # Report every source explicitly. A source returning nothing must look
    # different from a source that failed, and both must look different from a
    # source that was never consulted.
    inrange = {}
    for name, kind, rows, err in results:
        if err:
            print("%-20s: FETCH FAILED — %s" % (name, err), file=sys.stderr)
            continue
        hits = [r for r in rows if start <= r[0] <= end]
        inrange[name] = hits
        print("%-20s: %4d in range  (feed holds %d)" % (name, len(hits), len(rows)),
              file=sys.stderr)
    for name in MANUAL_SOURCES:
        print("%-20s: NO FEED — check by hand" % name, file=sys.stderr)

    combined = next((r for n, k, r, e in results if k == "daynotes" and not e), [])
    if combined:
        oldest = min(r[0] for r in combined)
        if oldest >= start:
            print("\n*** TRUNCATION WARNING ***", file=sys.stderr)
            print("Release Notes reaches back only to %s; you asked from %s."
                  % (oldest, start), file=sys.stderr)
            print("Items in range may have aged out unseen. This inventory is NOT "
                  "provably complete — do not publish it as one.", file=sys.stderr)
    print(file=sys.stderr)

    rows = [r for hits in inrange.values() for r in hits]
    if not rows:
        print("Nothing in range across any source.", file=sys.stderr)
        return 1

    by_day = collections.OrderedDict()
    for r in sorted(rows, key=lambda r: r[0], reverse=True):
        by_day.setdefault(r[0], []).append(r)

    out = io.StringIO()
    for day, items in by_day.items():
        out.write("\n## %s (%d)\n\n" % (day.strftime("%A %d %B %Y"), len(items)))
        if args.markdown:
            out.write("| Product | Type | Summary |\n|---|---|---|\n")
        for _d, product, kind, summary, link in sorted(items, key=lambda r: r[1]):
            if args.markdown:
                out.write("| %s | %s | [%s](%s) |\n" % (product, kind, summary, link))
            else:
                out.write("  %-34s %-12s %s\n" % (product[:34], kind[:12], summary))
    print(out.getvalue())
    print("TOTAL: %d notes across %d days (%s to %s)"
          % (len(rows), len(by_day), start, end), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
