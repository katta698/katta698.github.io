#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the AWS Monthly Intelligence report for a calendar month.

    python scripts/build_monthly_report.py 2026-08

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
"""
import datetime
import glob
import html
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_week import WHATS_NEW, fetch, parse                 # noqa: E402
# gists() lives with the weekly builder rather than the fetcher; import it from
# there instead of re-deriving it, so there is one definition of "AWS's own
# one-line summary" across the weekly and monthly documents.
from build_weekly_inventory import gists                       # noqa: E402

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

WEEKLY_RE = re.compile(
    r"weekly-\d+-(\d{4})-(\d{2})-(\d{2})-to-(\d{2})-(\d{2})\.html$")
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


def weekly_windows(year, month):
    """Published weekly roundups whose news window falls inside the month."""
    found = []
    for path in sorted(glob.glob(os.path.join(POSTS, "weekly-*.html"))):
        m = WEEKLY_RE.search(path.replace("\\", "/"))
        if not m:
            continue
        y, m1, d1, m2, d2 = (int(x) for x in m.groups())
        start = datetime.date(y, m1, d1)
        end = datetime.date(y, m2, d2)
        if start.year == year and start.month == month:
            found.append((start, end, path))
    return sorted(found)


def read_weekly_inventory(path, year):
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


def live_tail(first, last):
    """Announcements from the live feed for [first, last]. May be empty."""
    if first > last:
        return []
    raw = fetch(WHATS_NEW)
    summaries = gists(raw)
    rows = [r for r in parse(raw) if first <= r[0] <= last]
    return [(d, t, l, summaries.get(l, "")) for d, t, l in rows]


def feed_reach():
    """Oldest date the live What's New feed still carries."""
    rows = parse(fetch(WHATS_NEW))
    return min(r[0] for r in rows) if rows else None


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


def build(month_str):
    year, month = (int(x) for x in month_str.split("-"))
    first = datetime.date(year, month, 1)
    nxt = datetime.date(year + (month == 12), (month % 12) + 1, 1)
    last = nxt - datetime.timedelta(days=1)

    weeklies = weekly_windows(year, month)
    items = []
    covered = set()
    sources = []

    for start, end, path in weeklies:
        got, stated = read_weekly_inventory(path, year)
        items.extend(got)
        d = start
        while d <= end:
            covered.add(d)
            d += datetime.timedelta(days=1)
        # Reader-facing name. The filename is precise and is noise in a
        # document going to somebody who does not have the repository.
        label = "Weekly roundup, %s&ndash;%s" % (
            start.strftime("%#d" if os.name == "nt" else "%-d"),
            end.strftime("%#d %B" if os.name == "nt" else "%-d %B"))
        sources.append((label, start, end, len(got), stated))

    tail_from = max([e for _, e, _ in weeklies] or [first - datetime.timedelta(days=1)])
    tail_from += datetime.timedelta(days=1)
    reach = feed_reach()
    tail = live_tail(max(tail_from, reach or tail_from), last)
    items.extend(tail)
    if tail or tail_from <= last:
        d = max(tail_from, reach or tail_from)
        while d <= last:
            covered.add(d)
            d += datetime.timedelta(days=1)

    # Any weekday not covered by a roundup or by the live feed is a hole.
    missing = []
    d = first
    while d <= last:
        if d.weekday() < 5 and d not in covered:
            missing.append(d)
        d += datetime.timedelta(days=1)

    by_day = {}
    for it in items:
        by_day.setdefault(it[0], []).append(it)

    backlog = backlog_for_month(year, month)
    ranked = [r for rows in backlog.values() for r in rows]
    high = [r for r in ranked if r[3].lower().startswith(("high", "med-high"))]
    shipped = [r for r in ranked if r[2].strip().startswith("**#")]

    analysis_path = os.path.join(
        REPORTS, "aws-monthly-%s-analysis.html" % month_str)
    prose = {}
    if os.path.exists(analysis_path):
        text = io.open(analysis_path, encoding="utf-8").read()
        for key, _ in SECTIONS:
            m = re.search(r"<!--\s*%s\s*-->(.*?)(?=<!--|\Z)" % key, text,
                          re.S)
            if m:
                prose[key] = m.group(1).strip()

    os.makedirs(OUT, exist_ok=True)
    out_path = os.path.join(OUT, "aws-monthly-%s.html" % month_str)
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(
        render(first, last, by_day, sources, tail, missing, reach,
               ranked, high, shipped, prose))

    total = len(items)
    print("Month %s: %d announcements across %d day(s) with news"
          % (month_str, total, len(by_day)))
    for name, s, e, got, stated in sources:
        flag = "" if got == stated else "   (stated %d, parsed %d -- "\
                                        "unlinked 404 entries)" % (stated, got)
        print("  %-34s %s..%s  %3d%s"
              % (name.replace("&ndash;", "-"), s.isoformat(), e.isoformat(),
                 got, flag))
    if tail:
        print("  %-42s %s..%s  %3d"
              % ("live feed tail", tail[-1][0].isoformat(),
                 tail[0][0].isoformat(), len(tail)))
    print("  backlog: %d item(s) ranked, %d High/Med-High, %d became posts"
          % (len(ranked), len(high), len(shipped)))
    print("wrote %s" % out_path)
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


def render(first, last, by_day, sources, tail, missing, reach,
           ranked, high, shipped, prose):
    total = sum(len(v) for v in by_day.values())
    o = []
    a = o.append
    a("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>")
    a("<title>AWS Monthly Intelligence &mdash; %s</title>"
      % first.strftime("%B %Y"))
    a("<style>%s</style></head><body>" % CSS)

    a("<h1>AWS Monthly Intelligence</h1>")
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
    a("This report covers <strong>%d announcements</strong> from the AWS "
      "What's New feed, on %d days with news. " % (total, len(by_day)))
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
    if tail:
        days = sorted({t[0] for t in tail})
        a("<tr><td>live What's New feed</td><td>%s &ndash; %s</td>"
          "<td style='text-align:right'>%d</td></tr>"
          % (days[0].strftime("%d %b"), days[-1].strftime("%d %b"), len(tail)))
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
    a("<p>Every announcement in the month, newest first, with AWS's own "
      "one-line summary. This section exists so the coverage claim above can "
      "be checked rather than taken on trust.</p>")
    a("<div class='inv'>")
    for day in sorted(by_day, reverse=True):
        rows = by_day[day]
        a("<h4>%s &mdash; %d announcement%s</h4>"
          % (day.strftime("%A %d %B"), len(rows),
             "" if len(rows) == 1 else "s"))
        a("<ul>")
        for _d, title, url, gist in rows:
            if url:
                a('<li><a href="%s">%s</a><span class="gist">%s</span></li>'
                  % (html.escape(url, quote=True), html.escape(title),
                     html.escape(gist)))
            else:
                a('<li><strong>%s</strong><span class="gist">%s</span>'
                  '<span class="dead">AWS\'s own link for this announcement '
                  'returns 404 &mdash; recorded here for completeness.</span>'
                  '</li>' % (html.escape(title), html.escape(gist)))
        a("</ul>")
    a("</div>")

    a("<footer>Built by <code>scripts/build_monthly_report.py</code> from "
      "published weekly inventories and the live AWS What's New feed. "
      "Announcement text is AWS's own. Internal document.</footer>")
    a("</body></html>")
    return "\n".join(o)


def _md(s):
    """Markdown table cell -> plain text."""
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = s.replace("**", "").replace("`", "")
    return html.escape(s.strip())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(build(sys.argv[1]))
