#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a Monthly Intelligence report for a calendar month.

    python scripts/build_monthly_report.py 2026-08
    python scripts/build_monthly_report.py 2026-09 --cloud gcp

Writes a standalone printable HTML file to reports/out/. Open it and print to
PDF; nothing here touches posts/ or the publishing pipeline.

Why this cannot work the way the weekly builder works
-----------------------------------------------------
`build_weekly_inventory.py` fetches the What's New feed and filters to a date
range. That works for a week and **cannot** work for a month: the feed is capped
at 100 items, which was measured at a 12-day window in August 2026. Run on the
1st of the month, a live fetch reaches back to roughly the 19th of the previous
month and the first two-thirds of the month is simply gone -- with no error, and
no way for the output to know it is short.

So the month is assembled from the record rather than from the feed:

* **Published weekly roundups** (`posts/weekly-*.html`) for every complete
  Mon-Fri window in the month. Those inventories were built from the raw feed on
  the Saturday, with every link validated, which is exactly why the weekly
  series exists.
* **A live tail fetch** for the days after the last weekly window, where the
  feed still reaches.
* **`DAILY-BACKLOG.md`** for the importance ranking each item was given on the
  day, and for which items became daily deep-dives.

**Coverage is checked, not assumed.** Every weekday in the month must be covered
by a weekly inventory or by the live fetch. Any that is not is named in the
output and on stderr, and the script exits non-zero. A short month fails loudly
instead of looking complete -- which is the whole failure this file exists to
prevent.

The analysis prose is not generated
-----------------------------------
A month's worth of announcements has patterns in it, and finding them is the
part of this document worth reading. The script fills every data-derived
section and reads the prose from a sidecar you write:

    reports/aws-monthly-<YYYY-MM>-analysis.html

If that file is absent the report still builds, with the prose sections marked
as unwritten, so the data can be reviewed before the analysis is done.

Adding a cloud is a CLOUDS entry
--------------------------------
Everything that varies by cloud lives in the `CLOUDS` registry at the top of
this file: which roundups to read, how to parse one, where the live tail comes
from, whether there is a ranking backlog, and how to render the inventory.
Nothing below `build()` is cloud-specific. Adding a cloud must not fork the
file, because the part worth protecting -- the coverage assertion -- is the
part a fork would quietly diverge on.

Two things are genuinely different for GCP
------------------------------------------
**Volume.** Google Cloud publishes around 282 notes in a week against AWS's
~60, so a month is roughly 1,200 items and one row per item is not a document
anybody reads. The GCP inventory therefore carries the same three buckets the
weekly builder produces -- listed, published-under-several-products, and
repeating runs rolled up -- rather than a flat list.

**Roll up, never deduplicate.** Same-text/same-product notes are separate real
notes: Container Optimized OS fixes one kernel CVE once per milestone, so 131
notes can carry 49 distinct CVEs. Collapsing them under-counts the month. The
counts stay raw; only the rendering is folded. See CLAUDE.md and
`build_weekly_inventory_gcp.py`, which exists separately from the AWS builder
for exactly this reason.

**Links.** Most GCP notes share a day-anchor URL on the release-notes page
(`.../release-notes#August_24_2026`) rather than carrying their own; only Cloud
Blog items have a distinct link. So there is no per-item link to validate and
no 404-per-announcement case to render -- the AWS unlinked-item path does not
apply, and the day anchor is what a reader follows.
"""
import datetime
import glob
import html
import io
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_week import WHATS_NEW, fetch, parse                 # noqa: E402
# gists() lives with the weekly builder rather than the fetcher; import it from
# there instead of re-deriving it, so there is one definition of "AWS's own
# one-line summary" across the weekly and monthly documents.
from build_weekly_inventory import gists                       # noqa: E402
# The roll-up rules live with the GCP weekly builder. Import them rather than
# restating them, so "what counts as a repeating run" has one definition across
# the weekly and monthly documents -- the same reason gists() is imported above.
from build_weekly_inventory_gcp import classify, rollup_sentence  # noqa: E402
import fetch_week_gcp                                          # noqa: E402
import fetch_azure_week                                        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(ROOT, "posts")
REPORTS = os.path.join(ROOT, "reports")
OUT = os.path.join(REPORTS, "out")

# Prose sections the sidecar may supply, in the order they appear.
SECTIONS = [
    ("summary", "Executive summary"),
    ("actions", "What to act on"),
    ("trends", "What the month had in common"),
    ("lifecycle", "Lifecycle and deprecation calendar"),
]

# Both series name their roundups with the ISO news window, which is what makes
# a filename enough to establish coverage without parsing the post.
WEEKLY_RE = re.compile(
    r"weekly-\d+-(\d{4})-(\d{2})-(\d{2})-to-(\d{2})-(\d{2})\.html$")
GCPWEEKLY_RE = re.compile(
    r"gcpweekly-\d+-(\d{4})-(\d{2})-(\d{2})-to-(\d{2})-(\d{2})\.html$")
# The Azure series does not. Its slugs are written for a reader --
# azw-001-10-14-august-2026 -- so the window has to be recovered from day
# numbers and a month name rather than read off as ISO dates. Named groups mark
# it out, and weekly_windows() branches on `monthname` being present; the two
# ISO series keep their positional form untouched. The optional first month name
# is for a window that straddles a month boundary
# (azw-00N-31-august-4-september-2026), which has not occurred yet but is one
# Monday away: September 2026 begins on a Tuesday.
AZWEEKLY_RE = re.compile(
    r"azw-\d+-(?P<d1>\d{1,2})-(?:(?P<m1name>[a-z]+)-)?"
    r"(?P<d2>\d{1,2})-(?P<monthname>[a-z]+)-(?P<y>\d{4})\.html$")
DAY_RE = re.compile(r"<h3>(\w+day)\s+(\d{1,2})\s+(\w+)\s*&mdash;\s*(\d+)\s+"
                    r"announcements?</h3>")
LINKED_RE = re.compile(
    r'<li><a href="([^"]+)"><strong>(.*?)</strong></a>'
    r'<span class="inv-gist">(.*?)</span>')
UNLINKED_RE = re.compile(
    r'<li><strong>(.*?)</strong><span class="inv-gist">(.*?)</span>'
    r'<span class="inv-gist">AWS')


def _unescape(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _month_number(name):
    """Month number from a full month name, or None. Locale-independent."""
    try:
        return datetime.datetime.strptime(name.capitalize(), "%B").month
    except (ValueError, AttributeError):
        return None


def weekly_windows(cloud, year, month):
    """Published weekly roundups whose news window falls inside the month."""
    found = []
    for path in sorted(glob.glob(os.path.join(POSTS, cloud["weekly_glob"]))):
        m = cloud["weekly_re"].search(path.replace("\\", "/"))
        if not m:
            continue
        g = m.groupdict()
        if g.get("monthname"):
            # Reader-facing slug: day numbers and a month name, not ISO dates.
            year_ = int(g["y"])
            end_m = _month_number(g["monthname"])
            start_m = _month_number(g["m1name"]) if g.get("m1name") else end_m
            if not end_m or not start_m:
                continue
            start = datetime.date(year_, start_m, int(g["d1"]))
            end = datetime.date(year_, end_m, int(g["d2"]))
        else:
            y, m1, d1, m2, d2 = (int(x) for x in m.groups())
            start = datetime.date(y, m1, d1)
            end = datetime.date(y, m2, d2)
        if start.year == year and start.month == month:
            found.append((start, end, path))
    return sorted(found)


def read_weekly_inventory_aws(path, year):
    """(date, title, url_or_None, gist) for every item in one roundup."""
    text = io.open(path, encoding="utf-8").read()
    i = text.find('id="inventory"')
    if i < 0:
        return [], 0
    seg = text[i:]
    stated = re.search(r"<h2>Complete inventory: all (\d+) announcements</h2>",
                       seg)
    stated = int(stated.group(1)) if stated else 0

    items = []
    blocks = re.split(r"(?=<h3>)", seg)
    for block in blocks:
        head = DAY_RE.search(block)
        if not head:
            continue
        _, dom, monthname, _ = head.groups()
        try:
            day = datetime.datetime.strptime(
                "%s %s %d" % (dom, monthname, year), "%d %B %Y").date()
        except ValueError:
            continue
        for url, title, gist in LINKED_RE.findall(block):
            items.append((day, _unescape(title), html.unescape(url),
                          _unescape(gist)))
        for title, gist in UNLINKED_RE.findall(block):
            items.append((day, _unescape(title), None, _unescape(gist)))
    return items, stated


def live_tail_aws(first, last):
    """Announcements from the live feed for [first, last]. May be empty."""
    if first > last:
        return []
    raw = fetch(WHATS_NEW)
    summaries = gists(raw)
    rows = [r for r in parse(raw) if first <= r[0] <= last]
    return [(d, t, l, summaries.get(l, "")) for d, t, l in rows]


def feed_reach_aws():
    """Oldest date the live What's New feed still carries."""
    rows = parse(fetch(WHATS_NEW))
    return min(r[0] for r in rows) if rows else None


# --------------------------------------------------------------------------
# GCP
#
# A GCP roundup's inventory is already bucketed by build_weekly_inventory_gcp.py
# into listed / cross-product / rolled-up, so it is read back as those three
# buckets rather than flattened and re-bucketed. Flattening would lose the very
# thing the roll-up encodes: a run of 131 notes appears once, with its count and
# its identifiers intact, and there is no way to reconstitute the 131 rows from
# the rendered form. Re-rolling them would also be a no-op.
#
# The live tail is different: it has raw rows, so it goes through classify()
# and is bucketed by the same rules the weekly builder applied on the Saturday.
# --------------------------------------------------------------------------

GCP_LI_LISTED = re.compile(
    r'<li><a href="([^"]+)"><strong>(.*?)</strong></a>'
    r'<span class="inv-gist">(.*?)</span>'
    r'<span class="inv-gist">(.*?)</span></li>', re.S)
GCP_LI_ROLLED = re.compile(
    r'<li><a href="([^"]+)"><strong>(.*?) \((\d+) notes\)</strong></a>'
    r'\s*<em>&mdash; (.*?)</em><span class="inv-gist">(.*?)</span>', re.S)
GCP_LI_CROSS = re.compile(
    r'<li><a href="([^"]+)"><strong>(.*?)</strong></a>'
    r'<span class="inv-gist">(.*?)</span>'
    r'<span class="inv-gist">Published under (\d+) products: (.*?)</span>', re.S)
GCP_H4 = re.compile(r"<h4>(.*?) &mdash; \d+</h4>")


def _section(seg, heading):
    """The chunk of an inventory under one <h3>, or ''."""
    i = seg.find("<h3>%s" % heading)
    if i < 0:
        return ""
    j = seg.find("<h3>", i + 4)
    return seg[i:j if j > 0 else len(seg)]


def read_weekly_inventory_gcp(path, year):
    """(buckets, stated_total) for one published GCP roundup.

    `stated_total` comes from the section heading, which is the number the post
    itself claims and the number its own reconciliation table sums to. It is
    reported rather than recomputed, for the same reason the AWS reader reports
    the stated count: a mismatch between what the post said and what parses back
    is a fact worth surfacing, not one to paper over.
    """
    text = io.open(path, encoding="utf-8").read()
    i = text.find('id="inventory"')
    if i < 0:
        return {"listed": [], "cross": [], "rolled": []}, 0
    seg = text[i:]
    m = re.search(r"<h2>Complete inventory &mdash; all (\d+) notes?</h2>", seg)
    stated = int(m.group(1)) if m else 0

    rolled = []
    for url, product, n, kind, sentence in GCP_LI_ROLLED.findall(
            _section(seg, "Repeating runs, rolled up")):
        rolled.append((_unescape(product), _unescape(kind), int(n),
                       _unescape(sentence), html.unescape(url)))

    cross = []
    for url, kind, txt, _n, products in GCP_LI_CROSS.findall(
            _section(seg, "One change, published under several products")):
        cross.append((_unescape(kind), _unescape(txt),
                      [p.strip(" .") for p in _unescape(products).split(",")],
                      html.unescape(url)))

    listed = []
    by_product = _section(seg, "Everything else, by product")
    # Split on the product headings so each <li> is attributed to the <h4> it
    # sits under; the <li> itself carries the note type, not the product.
    chunks = GCP_H4.split(by_product)
    for k in range(1, len(chunks), 2):
        product = _unescape(chunks[k])
        for url, kind, gist, when in GCP_LI_LISTED.findall(chunks[k + 1]):
            listed.append((product, _unescape(kind), _unescape(gist),
                           _unescape(when), html.unescape(url)))
    return {"listed": listed, "cross": cross, "rolled": rolled}, stated


def _gcp_rows(first, last):
    """Raw (date, product, kind, summary, link, context) rows in range."""
    rows = []
    for _name, _kind, got, err in fetch_week_gcp.gather_ctx():
        if err:
            continue
        rows.extend(r for r in got if first <= r[0] <= last)
    return rows


def live_tail_gcp(first, last):
    """Buckets for the days after the last published roundup. May be empty."""
    empty = {"listed": [], "cross": [], "rolled": []}
    if first > last:
        return empty, 0
    rows = _gcp_rows(first, last)
    if not rows:
        return empty, 0
    cross, rolled, listed = classify(rows)
    out = {
        "listed": [(r[1], r[2], r[3], r[0].strftime("%a %d %b"), r[4])
                   for r in listed],
        "cross": [(g[0][2], text, sorted({x[1] for x in g}),
                   next((x[4] for x in g if x[4]), ""))
                  for text, g in cross.items()],
        "rolled": [(product, kind, len(g), rollup_sentence(g)[0],
                    next((x[4] for x in g if x[4]), ""))
                   for (product, kind), g in rolled.items()],
    }
    return out, len(rows)


def feed_reach_gcp():
    """Oldest date the combined release-notes feed still carries.

    Measured at 30 day-entries, which is a 30-day window because one entry is
    one calendar day. That is wider than AWS's 12 days but still short of a
    month, so the same assemble-from-the-record design applies.
    """
    days = [r[0] for r in fetch_week_gcp.parse_daynotes(
        fetch_week_gcp.fetch(fetch_week_gcp.COMBINED))]
    return min(days) if days else None


# --------------------------------------------------------------------------
# Azure
#
# An Azure roundup publishes its inventory as a table -- Date / Announcement /
# Status -- rather than as a day-grouped list, so DAY_RE, LINKED_RE and
# UNLINKED_RE match nothing against it and a separate reader is required. That
# is the only genuinely unshared part: the items come back in the same
# (date, title, url, note) shape the AWS reader produces, so everything below
# build() treats the two clouds identically.
#
# The fourth element is the **Status** Microsoft assigns -- GA, Preview,
# Retirement, Change -- where AWS carries a one-line summary. It is kept rather
# than dropped because neither of the other two clouds publishes it: a month's
# split between GA and Preview is the shape of the release stream, and a
# Retirement row is a dated commitment. Every row links, so the AWS
# unlinked-item path does not arise here.
#
# There is no roll-up. Azure published 14 announcements in the week of 24-28
# August, so a month is roughly 50 rows -- a list somebody will actually read,
# which is the condition the GCP bucketing exists to restore and this cloud
# never loses.
# --------------------------------------------------------------------------

AZ_ROW_RE = re.compile(
    r"<tr><td>(\d{1,2}\s+\w{3})</td>"
    r'<td><a href="([^"]+)"[^>]*>(.*?)</a></td>'
    r"<td>(.*?)</td></tr>", re.S)


def read_weekly_inventory_azure(path, year):
    """(date, title, url, status) for every row in one Azure roundup."""
    text = io.open(path, encoding="utf-8").read()
    i = text.find('id="inventory"')
    if i < 0:
        return [], 0
    seg = text[i:]
    m = re.search(r"<h2>Complete inventory &mdash; all (\d+)</h2>", seg)
    stated = int(m.group(1)) if m else 0

    items = []
    for datestr, url, title, status in AZ_ROW_RE.findall(seg):
        try:
            day = datetime.datetime.strptime(
                "%s %d" % (_unescape(datestr), year), "%d %b %Y").date()
        except ValueError:
            continue
        items.append((day, _unescape(title), html.unescape(url),
                      _unescape(status)))
    return items, stated


def live_tail_azure(first, last):
    """Announcements from the Azure Updates archive for [first, last].

    Uses fetch_azure_week.updates_in_range() rather than re-deriving the query,
    for the same reason gists() and classify() are imported above: one
    definition of "what was published in this range" across the weekly and
    monthly documents. That function returns (date, title, link) and no status,
    so tail rows carry an empty status -- the Status column is something the
    roundup's author records when writing it up, not something the range query
    returns.
    """
    if first > last:
        return []
    rows, _total, err = fetch_azure_week.updates_in_range(
        first.isoformat(), last.isoformat())
    if err:
        print("live tail: %s" % err, file=sys.stderr)
        return []
    return [(d, t, l, "") for d, t, l in rows]


def feed_reach_azure():
    """None -- the Azure Updates archive has no truncation window.

    The other two clouds read a capped feed, so their oldest available date is
    a real floor on what a live fetch can still recover. Azure's backbone is a
    JSON API whose date filter is evaluated server-side against the whole
    archive (measured at 9,873 records), so there is no floor to report and the
    tail can start wherever the published roundups stop.

    This does not make the month fetchable in one call, because build() only
    tails the days after the last roundup -- and it should not, since the
    roundup is the record. A month with a gap in that record still fails the
    coverage assertion, which is correct: the gap is in what was published, not
    in what the API can reach.
    """
    return None


def backlog_for_month(year, month):
    """{date: [(item, service, status, importance)]} from DAILY-BACKLOG.md."""
    path = os.path.join(ROOT, "DAILY-BACKLOG.md")
    if not os.path.exists(path):
        return {}
    text = io.open(path, encoding="utf-8").read()
    out = {}
    for chunk in re.split(r"(?=^## )", text, flags=re.M):
        head = re.match(r"## (\d{1,2}) (\w+) (\d{4})", chunk)
        if not head:
            continue
        try:
            day = datetime.datetime.strptime(
                "%s %s %s" % head.groups(), "%d %B %Y").date()
        except ValueError:
            continue
        if (day.year, day.month) != (year, month):
            continue
        rows = []
        for line in chunk.split("\n"):
            if not line.startswith("|") or line.startswith("| ---"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 4 or cells[0] == "Item":
                continue
            rows.append(cells[:4])
        out[day] = rows
    return out


# Where the finished PDF is delivered, so all three clouds land in one place
# regardless of which worktree built them. Each worktree has its own gitignored
# reports/out/ and nothing merges them -- without this you get three reports in
# three folders and have to go looking for them.
#
# An absolute path on purpose: Google Drive for Desktop mounts here, so any
# worktree can reach it. If the drive is not mounted the build still succeeds
# and says the PDF stayed local. A missing sync client is not a reason to fail
# a report that was otherwise produced correctly.
DELIVER_TO = r"K:\My Drive\Tech Notes & AWS\Monthly Intelligence"

# Rendered with a headless browser rather than a Python PDF library, because
# the report is already styled HTML with a print stylesheet -- Chrome applies
# @media print and paginates the tables, which is the output wanted.
BROWSERS = [
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


CLOUDS = {
    "aws": {
        "label": "AWS",
        "feed_name": "AWS What's New feed",
        "possessive": "AWS's",
        "unit": "announcement",
        "weekly_glob": "weekly-*.html",
        "weekly_re": WEEKLY_RE,
        "stem": "aws-monthly-%s",
        # AWS is the only one of the three with a daily series, so it is the
        # only one with a same-day ranking to report. None is a real answer
        # here, not a gap: there is no GCP daily intelligence series and one is
        # not planned (see CLAUDE.md).
        "backlog": "DAILY-BACKLOG.md",
        "read_inventory": read_weekly_inventory_aws,
        "live_tail": live_tail_aws,
        "feed_reach": feed_reach_aws,
        "flat_items": True,
        "item_note": "AWS's own one-line summary",
    },
    "gcp": {
        "label": "Google Cloud",
        "feed_name": "Google Cloud release notes, bulletins and blog "
                     "feeds",
        "possessive": "Google's",
        "unit": "note",
        "weekly_glob": "gcpweekly-*.html",
        "weekly_re": GCPWEEKLY_RE,
        "stem": "gcp-monthly-%s",
        "backlog": None,
        "read_inventory": read_weekly_inventory_gcp,
        "live_tail": live_tail_gcp,
        "feed_reach": feed_reach_gcp,
        "flat_items": False,
        "item_note": "Google's own text",
    },
    "azure": {
        "label": "Azure",
        "feed_name": "Azure Updates archive",
        "possessive": "Microsoft's",
        "unit": "announcement",
        "weekly_glob": "azw-*.html",
        "weekly_re": AZWEEKLY_RE,
        "stem": "azure-monthly-%s",
        # No Azure daily intelligence series exists and none is planned, so
        # there is no same-day ranking to report. None omits the section rather
        # than rendering it empty.
        "backlog": None,
        "read_inventory": read_weekly_inventory_azure,
        "live_tail": live_tail_azure,
        "feed_reach": feed_reach_azure,
        # ~14 announcements a week, so ~50 a month: one row per announcement is
        # a list a reader will finish, and there is nothing to roll up.
        "flat_items": True,
        "item_note": "the status Microsoft assigned it",
    },
}


def render_pdf(html_path):
    """Print the report to PDF with a headless browser. Returns the path.

    Not fatal if no browser is found: the HTML is the real artefact and can be
    printed by hand. A missing Chrome should not lose a correctly built report.
    """
    exe = next((b for b in BROWSERS if os.path.exists(b)), None)
    if not exe:
        print("  NOTE: no Chrome or Edge found; PDF not rendered.")
        return None
    pdf_path = os.path.splitext(html_path)[0] + ".pdf"
    url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
    rc = subprocess.call(
        [exe, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         "--print-to-pdf=" + pdf_path, url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if rc != 0 or not os.path.exists(pdf_path):
        print("  NOTE: the browser did not produce a PDF (exit %s)." % rc)
        return None
    return pdf_path


def deliver(pdf_path):
    """Copy the PDF to the shared delivery folder, if it is mounted."""
    if not pdf_path:
        return None
    drive = os.path.splitdrive(DELIVER_TO)[0] + os.sep
    if not os.path.isdir(drive):
        print("  NOTE: %s is not mounted; the PDF stayed in reports/out/."
              % drive)
        return None
    try:
        os.makedirs(DELIVER_TO, exist_ok=True)
        dest = os.path.join(DELIVER_TO, os.path.basename(pdf_path))
        shutil.copy2(pdf_path, dest)
        return dest
    except OSError as exc:                                     # noqa: BLE001
        print("  NOTE: could not deliver to %s (%s)." % (DELIVER_TO, exc))
        return None


def build(month_str, cloud_key="aws"):
    cloud = CLOUDS[cloud_key]
    year, month = (int(x) for x in month_str.split("-"))
    first = datetime.date(year, month, 1)
    nxt = datetime.date(year + (month == 12), (month % 12) + 1, 1)
    last = nxt - datetime.timedelta(days=1)

    weeklies = weekly_windows(cloud, year, month)
    flat = cloud["flat_items"]
    items = []
    buckets = {"listed": [], "cross": [], "rolled": []}
    total = 0
    covered = set()
    sources = []

    for start, end, path in weeklies:
        got, stated = cloud["read_inventory"](path, year)
        if flat:
            items.extend(got)
            n = len(got)
        else:
            for k in buckets:
                buckets[k].extend(got[k])
            # The post's own stated total is authoritative for the month total.
            # A rolled-up run renders as one entry standing for many notes, so
            # counting entries would under-count exactly the runs the roll-up
            # exists to fold.
            n = stated
        total += stated if not flat else len(got)
        d = start
        while d <= end:
            covered.add(d)
            d += datetime.timedelta(days=1)
        # Reader-facing name. The filename is precise and is noise in a
        # document going to somebody who does not have the repository.
        label = "Weekly roundup, %s&ndash;%s" % (
            start.strftime("%#d" if os.name == "nt" else "%-d"),
            end.strftime("%#d %B" if os.name == "nt" else "%-d %B"))
        sources.append((label, start, end, n, stated))

    tail_from = max([e for _, e, _ in weeklies] or [first - datetime.timedelta(days=1)])
    tail_from += datetime.timedelta(days=1)
    reach = cloud["feed_reach"]()
    tail_start = max(tail_from, reach or tail_from)
    if flat:
        tail = cloud["live_tail"](tail_start, last)
        items.extend(tail)
        tail_n = len(tail)
    else:
        tail_buckets, tail_n = cloud["live_tail"](tail_start, last)
        for k in buckets:
            buckets[k].extend(tail_buckets[k])
        tail = tail_buckets if tail_n else None
        total += tail_n
    if tail_n or tail_from <= last:
        d = tail_start
        while d <= last:
            covered.add(d)
            d += datetime.timedelta(days=1)

    # Any weekday not covered by a roundup or by the live feed is a hole.
    # Unchanged and deliberately shared: this is the assertion the document
    # rests on, and it is the one thing a per-cloud fork would drift on.
    missing = []
    d = first
    while d <= last:
        if d.weekday() < 5 and d not in covered:
            missing.append(d)
        d += datetime.timedelta(days=1)

    by_day = {}
    for it in items:
        by_day.setdefault(it[0], []).append(it)
    if flat:
        total = len(items)

    backlog = backlog_for_month(year, month) if cloud["backlog"] else {}
    ranked = [r for rows in backlog.values() for r in rows]
    high = [r for r in ranked if r[3].lower().startswith(("high", "med-high"))]
    shipped = [r for r in ranked if r[2].strip().startswith("**#")]

    analysis_path = os.path.join(
        REPORTS, (cloud["stem"] % month_str) + "-analysis.html")
    prose = {}
    if os.path.exists(analysis_path):
        text = io.open(analysis_path, encoding="utf-8").read()
        for key, _ in SECTIONS:
            m = re.search(r"<!--\s*%s\s*-->(.*?)(?=<!--|\Z)" % key, text,
                          re.S)
            if m:
                prose[key] = m.group(1).strip()

    os.makedirs(OUT, exist_ok=True)
    out_path = os.path.join(OUT, (cloud["stem"] % month_str) + ".html")
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(
        render(cloud, first, last, by_day, buckets, total, sources, tail,
               tail_n, missing, reach, ranked, high, shipped, prose))

    print("Month %s (%s): %d %s%s across %d source(s)"
          % (month_str, cloud["label"], total, cloud["unit"],
             "" if total == 1 else "s", len(sources) + (1 if tail_n else 0)))
    for name, s_, e_, got, stated in sources:
        flag = "" if got == stated else "   (stated %d, parsed %d -- "                                        "unlinked 404 entries)" % (stated, got)
        print("  %-34s %s..%s  %4d%s"
              % (name.replace("&ndash;", "-"), s_.isoformat(), e_.isoformat(),
                 got, flag))
    if tail_n:
        print("  %-34s %s..%s  %4d"
              % ("live feed tail", tail_start.isoformat(), last.isoformat(),
                 tail_n))
    if not flat:
        print("  buckets: %d listed, %d cross-product, %d rolled-up run(s)"
              % (len(buckets["listed"]), len(buckets["cross"]),
                 len(buckets["rolled"])))
    if cloud["backlog"]:
        print("  backlog: %d item(s) ranked, %d High/Med-High, %d became posts"
              % (len(ranked), len(high), len(shipped)))
    print("wrote %s" % out_path)
    pdf = render_pdf(out_path)
    if pdf:
        print("wrote %s" % pdf)
        dest = deliver(pdf)
        if dest:
            print("delivered %s" % dest)
    if not prose:
        print("  NOTE: no analysis sidecar at %s -- prose sections are marked "
              "unwritten." % os.path.relpath(analysis_path, ROOT))
    if missing:
        print("\nCOVERAGE HOLE -- these weekdays are in neither a published "
              "roundup nor the live feed:", file=sys.stderr)
        for d in missing:
            print("   %s" % d.isoformat(), file=sys.stderr)
        print("The feed reaches back only to %s, so those days cannot be "
              "recovered now." % (reach.isoformat() if reach else "?"),
              file=sys.stderr)
        return 1
    return 0


CSS = """
:root{--ink:#1D2322;--mut:#6B6560;--line:#C9C3BC;--bg:#F8F7F5;--tan:#C4A484;
--warn:#B5654A;--ok:#8A9A5B}
*{box-sizing:border-box}
body{font-family:Georgia,'Times New Roman',serif;color:var(--ink);
background:#fff;margin:0;padding:48px 56px;line-height:1.55;font-size:15px}
h1{font-size:30px;margin:0 0 4px;letter-spacing:-.01em}
h2{font-size:19px;margin:38px 0 12px;padding-bottom:6px;
border-bottom:2px solid var(--tan)}
h3{font-size:14px;margin:22px 0 8px;color:var(--mut);
text-transform:uppercase;letter-spacing:.06em}
.sub{color:var(--mut);font-size:14px;margin:0 0 2px}
.rule{height:3px;background:var(--tan);margin:18px 0 26px;max-width:120px}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:13.5px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);
vertical-align:top}
th{background:var(--bg);font-size:12px;text-transform:uppercase;
letter-spacing:.05em;color:var(--mut)}
.p0{color:var(--warn);font-weight:bold}
.box{background:var(--bg);border:1px solid var(--line);border-left:4px solid
var(--tan);padding:14px 16px;margin:16px 0;font-size:14px}
.box.warn{border-left-color:var(--warn)}
.box.ok{border-left-color:var(--ok)}
.unwritten{background:#fff6f2;border-left-color:var(--warn);color:var(--warn);
font-style:italic}
ul{margin:10px 0;padding-left:22px}li{margin:5px 0}
.inv h4{font-size:13px;margin:18px 0 6px;color:var(--ink);
border-bottom:1px solid var(--line);padding-bottom:4px}
.inv ul{list-style:none;padding-left:0;margin:0}
.inv li{margin:0 0 9px;font-size:12.5px;line-height:1.45}
.inv a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--tan)}
.gist{display:block;color:var(--mut);font-size:11.5px;margin-top:2px}
.dead{color:var(--warn);font-size:11px}
footer{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);
color:var(--mut);font-size:12px}
@media print{body{padding:0;font-size:11.5pt}h2{page-break-after:avoid}
.inv li{page-break-inside:avoid}a{color:var(--ink)}
h1{page-break-after:avoid}.box{page-break-inside:avoid}}
"""


def render(cloud, first, last, by_day, buckets, total, sources, tail, tail_n,
           missing, reach, ranked, high, shipped, prose):
    o = []
    a = o.append
    a("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>")
    a("<title>%s Monthly Intelligence &mdash; %s</title>"
      % (cloud["label"], first.strftime("%B %Y")))
    a("<style>%s</style></head><body>" % CSS)

    a("<h1>%s Monthly Intelligence</h1>" % cloud["label"])
    a("<p class='sub'>%s</p>" % first.strftime("%B %Y"))
    a("<p class='sub'>Coverage %s to %s &middot; prepared %s</p>"
      % (first.strftime("%-d %B") if os.name != "nt"
         else first.strftime("%#d %B"),
         last.strftime("%#d %B %Y") if os.name == "nt"
         else last.strftime("%-d %B %Y"),
         datetime.date.today().strftime("%#d %B %Y") if os.name == "nt"
         else datetime.date.today().strftime("%-d %B %Y")))
    a("<div class='rule'></div>")

    # Completeness, stated up front. This is the claim the document rests on.
    a("<div class='box %s'>" % ("warn" if missing else "ok"))
    a("<strong>Completeness</strong><br>")
    a("This report covers <strong>%d %s%s</strong> from the %s%s. "
      % (total, cloud["unit"], "" if total == 1 else "s", cloud["feed_name"],
         ", on %d days with news" % len(by_day) if cloud["flat_items"] else ""))
    if missing:
        a("<strong>%d weekday(s) could not be covered</strong>: %s. The live "
          "feed reaches back only to %s."
          % (len(missing), ", ".join(d.strftime("%-d %b") if os.name != "nt"
                                     else d.strftime("%#d %b")
                                     for d in missing),
             reach.isoformat() if reach else "unknown"))
    else:
        a("Every weekday in the month is accounted for, from the sources "
          "below. Nothing is sampled and nothing is summarised by hand &mdash; "
          "the inventory is the feed.")
    a("</div>")

    a("<table><thead><tr><th>Source</th><th>Window</th>"
      "<th style='text-align:right'>Announcements</th></tr></thead><tbody>")
    for name, s, e, got, stated in sources:
        a("<tr><td>%s</td><td>%s &ndash; %s</td>"
          "<td style='text-align:right'>%d</td></tr>"
          % (name, s.strftime("%d %b"), e.strftime("%d %b"),
             stated or got))
    if tail_n and cloud["flat_items"]:
        days = sorted({t[0] for t in tail})
        a("<tr><td>live What's New feed</td><td>%s &ndash; %s</td>"
          "<td style='text-align:right'>%d</td></tr>"
          % (days[0].strftime("%d %b"), days[-1].strftime("%d %b"), tail_n))
    elif tail_n:
        a("<tr><td>live feed tail</td><td>after the last roundup</td>"
          "<td style='text-align:right'>%d</td></tr>" % tail_n)
    a("<tr><th>Total</th><th></th><th style='text-align:right'>%d</th></tr>"
      % total)
    a("</tbody></table>")

    for key, title in SECTIONS:
        a("<h2>%s</h2>" % title)
        if key in prose:
            a(prose[key])
        else:
            a("<div class='box unwritten'>Not yet written. Add a "
              "<code>&lt;!-- %s --&gt;</code> block to the analysis sidecar "
              "and rebuild.</div>" % key)

    if ranked:
        a("<h2>How the month was ranked at the time</h2>")
        a("<p>Every announcement was ranked on the day it landed, in "
          "<code>DAILY-BACKLOG.md</code>. Of <strong>%d</strong> items ranked "
          "this month, <strong>%d</strong> were High or Med-High and "
          "<strong>%d</strong> became a same-week deep-dive.</p>"
          % (len(ranked), len(high), len(shipped)))
        a("<table><thead><tr><th>Item</th><th>Service</th>"
          "<th>Importance</th></tr></thead><tbody>")
        for item, service, _status, imp in high[:40]:
            a("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
              % (_md(item), _md(service), _md(imp)))
        a("</tbody></table>")

    a("<h2>Complete inventory</h2>")
    if cloud["flat_items"]:
        # Cloud-specific wording comes from the registry rather than from a
        # branch here: two clouds now render flat, and a branch is how the
        # second one quietly diverges from the first.
        a("<p>Every %s in the month, newest first, with %s. This section "
          "exists so the coverage claim above can be checked rather than "
          "taken on trust.</p>" % (cloud["unit"], cloud["item_note"]))
        a("<div class='inv'>")
        for day in sorted(by_day, reverse=True):
            rows = by_day[day]
            a("<h4>%s &mdash; %d %s%s</h4>"
              % (day.strftime("%A %d %B"), len(rows), cloud["unit"],
                 "" if len(rows) == 1 else "s"))
            a("<ul>")
            for _d, title, url, gist in rows:
                if url:
                    a('<li><a href="%s">%s</a><span class="gist">%s</span></li>'
                      % (html.escape(url, quote=True), html.escape(title),
                         html.escape(gist)))
                else:
                    a('<li><strong>%s</strong><span class="gist">%s</span>'
                      '<span class="dead">%s own link for this %s returns '
                      '404 &mdash; recorded here for completeness.</span></li>'
                      % (html.escape(title), html.escape(gist),
                         cloud["possessive"], cloud["unit"]))
            a("</ul>")
        a("</div>")
    else:
        _render_inventory_gcp(a, buckets, total)

    a("<footer>Built by <code>scripts/build_monthly_report.py</code> from "
      "published weekly inventories and the live %s. %s text is %s own. "
      "Internal document.</footer>"
      % (cloud["feed_name"], cloud["unit"].capitalize(), cloud["possessive"]))
    a("</body></html>")
    return "\n".join(o)


def _render_inventory_gcp(a, buckets, total):
    """The month's notes, in the three buckets the weekly builder produces.

    Deliberately not one row per note. A GCP month is roughly 1,200 notes and
    over half of a typical week is a single product's kernel CVE run, so a flat
    list is long enough that nobody checks it -- which defeats the only reason
    the section exists. Nothing is dropped: a rolled-up run states its own raw
    count and lists its identifiers, so the arithmetic still reconciles.
    """
    listed, cross, rolled = (buckets["listed"], buckets["cross"],
                             buckets["rolled"])
    rolled_n = sum(r[2] for r in rolled)
    # One cross-product entry stands for one note per product it was published
    # under, so the product list is the note count. Recovering it is what lets
    # the three buckets sum to the month total rather than leaving a gap the
    # reader has to take on trust.
    cross_n = sum(len(c[2]) for c in cross)
    accounted = len(listed) + cross_n + rolled_n
    a("<p>Every note Google Cloud published in the month, in the same three "
      "buckets each weekly roundup uses. Runs that repeat the same text once "
      "per release are folded into a single entry that states its raw count "
      "and names the releases &mdash; folded, never deduplicated, because "
      "same-text notes under one product are separate real notes and "
      "collapsing them would under-count the month.</p>")

    a("<table><thead><tr><th>Bucket</th>"
      "<th style='text-align:right'>Notes</th><th>Rendering</th></tr></thead>"
      "<tbody>")
    a("<tr><td>Listed individually</td><td style='text-align:right'>%d</td>"
      "<td>One row each, grouped by product.</td></tr>" % len(listed))
    a("<tr><td>Published under several products</td>"
      "<td style='text-align:right'>%d</td><td>%d text%s shown once, with "
      "the products named.</td></tr>"
      % (cross_n, len(cross), "" if len(cross) == 1 else "s"))
    a("<tr><td>Repeating runs, rolled up</td>"
      "<td style='text-align:right'>%d</td><td>%d run%s, each stating its raw "
      "count.</td></tr>"
      % (rolled_n, len(rolled), "" if len(rolled) == 1 else "s"))
    a("<tr><th>Month total</th><th style='text-align:right'>%d</th>"
      "<th></th></tr>" % total)
    a("</tbody></table>")
    # The buckets are the completeness claim, so a gap is stated rather than
    # left for the reader to find by subtracting. It is not fatal -- the
    # coverage assertion above is the blocking check -- but an inventory whose
    # own arithmetic does not close should say so on its face.
    if accounted != total:
        a("<div class='box warn'><strong>Buckets do not sum</strong><br>"
          "The buckets above account for %d of %d notes, a difference of %d. "
          "Every note is still in exactly one bucket; the gap means a "
          "published roundup rendered a count this report could not parse "
          "back.</div>" % (accounted, total, abs(total - accounted)))

    a("<div class='inv'>")
    if rolled:
        a("<h4>Repeating runs, rolled up &mdash; %d notes</h4>" % rolled_n)
        a("<ul>")
        for product, kind, n, sentence, url in sorted(
                rolled, key=lambda r: -r[2]):
            head = "%s (%d notes) &mdash; %s" % (html.escape(product), n,
                                                 html.escape(kind))
            a("<li>%s<span class='gist'>%s</span></li>"
              % (_link(head, url), html.escape(sentence)))
        a("</ul>")

    if cross:
        a("<h4>One change, published under several products &mdash; %d</h4>"
          % len(cross))
        a("<ul>")
        for kind, text, products, url in cross:
            a("<li>%s<span class='gist'>%s</span>"
              "<span class='gist'>Published under %d products: %s.</span></li>"
              % (_link(html.escape(kind), url), html.escape(text),
                 len(products), html.escape(", ".join(products))))
        a("</ul>")

    if listed:
        a("<h4>Everything else, by product &mdash; %d</h4>" % len(listed))
        by_product = {}
        for product, kind, gist, when, url in listed:
            by_product.setdefault(product, []).append((kind, gist, when, url))
        for product in sorted(by_product):
            rows = by_product[product]
            a("<h4>%s &mdash; %d</h4>" % (html.escape(product), len(rows)))
            a("<ul>")
            for kind, gist, when, url in rows:
                a("<li>%s<span class='gist'>%s</span>"
                  "<span class='gist'>%s</span></li>"
                  % (_link(html.escape(kind), url), html.escape(gist),
                     html.escape(when)))
            a("</ul>")
    a("</div>")


def _link(inner, url):
    """A day anchor, or plain text where a note has no link.

    Unlike AWS, a GCP note usually has no URL of its own -- it shares the day
    anchor on the release-notes page, and only Cloud Blog items carry a
    distinct one. So there is nothing here to validate per announcement and no
    per-item 404 case: a missing link means the source had none, not that the
    vendor's link is broken.
    """
    if not url:
        return "<strong>%s</strong>" % inner
    return '<a href="%s">%s</a>' % (html.escape(url, quote=True), inner)


def _md(s):
    """Markdown table cell -> plain text."""
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = s.replace("**", "").replace("`", "")
    return html.escape(s.strip())


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:]]
    cloud = "aws"
    if "--cloud" in argv:
        i = argv.index("--cloud")
        cloud = argv[i + 1]
        del argv[i:i + 2]
    if not argv or cloud not in CLOUDS:
        print(__doc__)
        sys.exit(2)
    sys.exit(build(argv[0], cloud))
