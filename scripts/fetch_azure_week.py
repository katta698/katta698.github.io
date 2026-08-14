#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull a complete, deterministic inventory of what Azure published in a date range.

Why this exists
---------------
Same promise as `fetch_week.py` makes for AWS: the Azure Weekly Intelligence post
tells a reader they do not need to check anywhere else, and that promise rests
entirely on the source list being right. A source absent from this file cannot
be noticed as missing at run time.

The AWS series learned that twice, expensively — a model asked to summarise the
feed missed 24 of 66 announcements in one week, and a source list of two feeds
left ~170 posts unread for a month. Neither errored. This script inherits the
fix: parse machine-readable sources, all of them, no judgement.

What is different about Azure
-----------------------------
**The documented feed is a trap.** `https://azure.microsoft.com/en-us/updates/feed/`
answers HTTP 200 and returns **HTML**, not RSS. Anything that trusts the status
code, or that catches the parse error and moves on, silently reads nothing from
the single most important Azure source. Measured 2026-08-14.

**The real backbone is a JSON API**, not a feed:

    https://www.microsoft.com/releasecommunications/api/v2/azure

It is OData, it supports `$filter` on `created`, and it holds the full archive —
9,845 records on 2026-08-14. That is a materially better position than AWS's
What's New feed, which caps at 100 items and 12 days: **there is no truncation
window on the Azure backbone**, because the range is queried rather than sliced
off the top of a fixed-size feed.

**Its RSS twin is not a substitute.** `.../azure/rss` carries exactly 200 items
and agrees with the API precisely — for nine weeks. Measured 2026-08-14, week by
week:

    2026-06-08 onward .............. RSS matches the API exactly
    2026-06-01 to 06-07 ............ API 166, RSS 91   (short by 75)
    2026-05-25 and earlier ......... API 5-22 a week, RSS **zero**

So the RSS does not degrade gracefully at its limit; past it, it reports weeks
as empty that were not. A weekly roundup built on it would have been correct for
two months and then quietly wrong forever. The API is the source of truth here;
the RSS is kept only as a cross-check, and `--audit` re-measures where the two
part company so the boundary is a measurement rather than a memory.

Usage
-----
    python scripts/fetch_azure_week.py                    # the last 7 days
    python scripts/fetch_azure_week.py 2026-08-10 2026-08-14
    python scripts/fetch_azure_week.py --markdown         # paste into a post
    python scripts/fetch_azure_week.py --audit            # probe every source
    python scripts/fetch_azure_week.py --audit --deep     # also re-measure the
                                                          # RSS divergence point
"""
import argparse
import collections
import concurrent.futures
import datetime
import email.utils
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# Microsoft's edge returns 403 to a bare "Mozilla/5.0" on some hosts and 200 to
# a full browser string. Not worth arguing with; measured 2026-08-14.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

UPDATES_API = "https://www.microsoft.com/releasecommunications/api/v2/azure"
UPDATES_RSS = UPDATES_API + "/rss"

TC = "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=%s"

# Every Azure source with a machine-readable feed, verified by probe on
# 2026-08-14. Adding a source here is the only way it gets read; there is no
# discovery. Re-probe with --audit when a roundup feels thin.
#
# The Azure Updates backbone is deliberately NOT in this list — it is a JSON API
# rather than a feed and is fetched separately by updates_in_range().
SOURCES = [
    ("Azure Updates (RSS)",  UPDATES_RSS),
    ("Azure Blog",           "https://azure.microsoft.com/en-us/blog/feed/"),

    # Security. The MSRC update guide is the CVE firehose for all Microsoft
    # products, not only Azure — thousands of items, filtered by date here and
    # by judgement when writing.
    ("MSRC Update Guide",    "https://api.msrc.microsoft.com/update-guide/rss"),
    ("Microsoft Security",   "https://www.microsoft.com/en-us/security/blog/feed/"),

    # Engineering blogs.
    ("Azure SDK",            "https://devblogs.microsoft.com/azure-sdk/feed/"),
    ("Azure DevOps",         "https://devblogs.microsoft.com/devops/feed/"),
    ("Cosmos DB",            "https://devblogs.microsoft.com/cosmosdb/feed/"),
    ("Azure SQL (devblog)",  "https://devblogs.microsoft.com/azure-sql/feed/"),
    ("Identity (devblog)",   "https://devblogs.microsoft.com/identity/feed/"),
    ("Azure Government",     "https://devblogs.microsoft.com/azuregov/feed/"),
    ("ISE",                  "https://devblogs.microsoft.com/ise/feed/"),

    # Tech Community boards. Two id styles coexist since the 2025 platform
    # change — PascalCase for older boards, kebab-case for newer ones. Both are
    # live; neither form is being migrated, so do not "normalise" them.
    ("TC Infrastructure",    TC % "AzureInfrastructureBlog"),
    ("TC Networking",        TC % "AzureNetworkingBlog"),
    ("TC Network Security",  TC % "AzureNetworkSecurityBlog"),
    ("TC Compute",           TC % "AzureCompute"),
    ("TC Architecture",      TC % "AzureArchitectureBlog"),
    ("TC Storage",           TC % "AzureStorageBlog"),
    ("TC Governance",        TC % "AzureGovernanceandManagementBlog"),
    ("TC Apps on Azure",     TC % "AppsonAzureBlog"),
    ("TC PaaS",              TC % "AzurePaaSBlog"),
    ("TC Integration",       TC % "IntegrationsonAzureBlog"),
    ("TC Observability",     TC % "AzureObservabilityBlog"),
    ("TC Arc",               TC % "AzureArcBlog"),
    ("TC Migration",         TC % "AzureMigrationBlog"),
    ("TC FastTrack",         TC % "FastTrackforAzureBlog"),
    ("TC Virtual Desktop",   TC % "AzureVirtualDesktopBlog"),
    ("TC HPC",               TC % "AzureHighPerformanceComputingBlog"),
    ("TC Confidential",      TC % "AzureConfidentialComputingBlog"),
    ("TC PostgreSQL",        TC % "ADforPostgreSQL"),
    ("TC MySQL",             TC % "ADforMySQL"),
    ("TC Azure SQL",         TC % "AzureSQLBlog"),
    ("TC Entra",             TC % "microsoft-entra-blog"),
    ("TC AI Foundry",        TC % "azure-ai-foundry-blog"),
    ("TC Defender for Cloud", TC % "MicrosoftDefenderCloudBlog"),
    ("TC Sentinel",          TC % "MicrosoftSentinelBlog"),
    ("TC ITOps Talk",        TC % "ITOpsTalkBlog"),
    ("TC Core Infra",        TC % "CoreInfrastructureandSecurityBlog"),
    ("TC Dev Community",     TC % "AzureDevCommunityBlog"),

    # Release notes. Version-level detail the announcement omits.
    ("AKS releases",         "https://github.com/Azure/AKS/releases.atom"),
    ("Azure CLI releases",   "https://github.com/Azure/azure-cli/releases.atom"),
    ("Bicep releases",       "https://github.com/Azure/bicep/releases.atom"),
    ("Terraform AzureRM",    "https://github.com/hashicorp/terraform-provider-azurerm/releases.atom"),
]

# Sources with no working machine-readable feed found on 2026-08-14. Listed so
# the gap is visible on every run rather than silently absent. The board ids
# below were each probed and returned an empty feed — the blogs exist, their RSS
# ids do not follow either naming convention, and the Tech Community blog
# directory is client-rendered so the id cannot be scraped.
#
# Probed and empty: AzureKubernetesServiceBlog, AKSBlog, Azure-Kubernetes-Service,
# AzureVMwareSolutionBlog, AzureVMwareSolution, FabricBlog, AzureAIServicesBlog.
MANUAL_SOURCES = (
    "AKS blog (Tech Community) — release notes feed covers the versions",
    "Azure VMware Solution blog",
    "Microsoft Fabric blog",
    "Ignite / Build announcements",
)


# The MSRC update guide is the CVE feed for *every* Microsoft product, and it is
# enormous: 5,014 items, of which 847 fell in the five days 10-14 August 2026.
# Five of those 847 were Azure. The rest were Excel, SharePoint, Windows Kernel,
# Exchange and the rest of Patch Tuesday.
#
# Dropping the source was the other option and it is the wrong one — Azure CVEs
# are exactly the kind of thing a weekly roundup should carry, and a source
# removed for being noisy is a source nobody notices has gone. So it is filtered
# to Azure products, and **the number suppressed is printed on every run**. A
# silent filter is the same failure as a missing feed wearing a different hat.
#
# The risk this carries: a new Azure service whose name is not below is
# invisible. Two mitigations — the suppressed count makes the filter's existence
# obvious, and --msrc-all turns it off to check what is being dropped. Review
# this list when Azure ships a service with an unfamiliar name.
AZURE_CVE_RE = re.compile(
    r"\b(azure|entra|aks|kubernetes service|cosmos ?db|service fabric|"
    r"sentinel|defender for cloud|defender for endpoint|app service|synapse|"
    r"databricks|logic apps|api management|key vault|arc|hdinsight|"
    r"microsoft fabric|power bi embedded|virtual desktop|dev ?box|"
    r"application gateway|front door|event hubs|service bus|data factory|"
    r"machine learning|openai|copilot studio|purview|monitor agent)\b", re.I)

MSRC_NAME = "MSRC Update Guide"


def fetch(url, attempts=3):
    """Fetch with bounded retries on transient failures.

    Microsoft's edge intermittently answers 503 to a request that succeeds
    moments later — observed on azure.microsoft.com/blog/feed/ during a run
    whose immediate retry succeeded four times out of four. Without this, a
    blip is indistinguishable from a dead source, and the whole value of the
    audit is that those two look different.

    Only transient statuses are retried. A 404 or a 403 is a real answer and is
    raised immediately, because it means the source list is wrong.
    """
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or i == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if i == attempts - 1:
                raise
        time.sleep(2 * (i + 1))


def _date(text):
    """RSS and Atom disagree about date format. Accept both."""
    if not text:
        return None
    text = text.strip()
    try:
        if "T" in text and "," not in text:
            return datetime.datetime.fromisoformat(
                text.replace("Z", "+00:00")).date()
        return email.utils.parsedate_to_datetime(text).date()
    except Exception:                                          # noqa: BLE001
        return None


ATOM = "{http://www.w3.org/2005/Atom}"


def parse(raw):
    """Return [(date, title, link)] newest first, from RSS or Atom.

    A feed that parses as XML but yields no items is not an error here — it is
    reported as an empty feed, which is exactly the state that must stay
    visible. Several Tech Community boards answer 200 with a valid but empty
    document when the board id is wrong.
    """
    root = ET.fromstring(raw)
    out = []
    for it in root.findall(".//item"):
        d = _date(it.findtext("pubDate"))
        if d:
            out.append((d, (it.findtext("title") or "").strip(),
                        (it.findtext("link") or "").strip()))
    for it in root.findall(".//%sentry" % ATOM):
        d = _date(it.findtext("%supdated" % ATOM)
                  or it.findtext("%spublished" % ATOM))
        if not d:
            continue
        link = ""
        el = it.find("%slink" % ATOM)
        if el is not None:
            link = el.get("href", "")
        out.append((d, (it.findtext("%stitle" % ATOM) or "").strip(), link))
    return sorted(out, key=lambda r: r[0], reverse=True)


def load(name_url):
    """Fetch and parse one source. Never raises — a dead feed must be reported,
    not crash the run, and must never look like an empty one either."""
    name, url = name_url
    try:
        return name, parse(fetch(url)), None
    except Exception as exc:                                   # noqa: BLE001
        return name, [], "%s: %s" % (type(exc).__name__, str(exc)[:80])


def gather():
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        return list(pool.map(load, SOURCES))


def updates_in_range(start, end):
    """The Azure Updates backbone, queried by date rather than sliced.

    Returns (rows, total_records, error). `rows` is [(date, title, link)].

    This is the whole reason the series can promise completeness: the filter is
    evaluated server-side against the full archive, so there is no window past
    which items are unreachable. Paged defensively — Build week 2026 produced
    166 announcements in seven days.
    """
    rows, total, skip = [], None, 0
    try:
        while True:
            flt = ("created ge %sT00:00:00Z and created le %sT23:59:59Z"
                   % (start, end))
            url = UPDATES_API + "?" + urllib.parse.urlencode({
                "$filter": flt, "$count": "true", "$top": "200", "$skip": skip})
            page = json.loads(fetch(url))
            total = page.get("@odata.count", total)
            batch = page.get("value") or []
            for r in batch:
                d = _date(str(r.get("created", ""))[:19] + "Z")
                if not d:
                    continue
                # Microsoft's own canonical form, taken from the <link> its RSS
                # publishes: no locale segment, id as a query parameter. The
                # page is client-rendered, so every id — real or invented —
                # returns the same 199 KB shell. Byte size cannot validate
                # these links; only the id can, and it comes from this API.
                rows.append((d, str(r.get("title", "")).strip(),
                             "https://azure.microsoft.com/updates?id=%s"
                             % r.get("id", "")))
            skip += len(batch)
            if not batch or skip >= (total or 0):
                break
        return sorted(rows, key=lambda r: r[0], reverse=True), total, None
    except Exception as exc:                                   # noqa: BLE001
        return [], None, "%s: %s" % (type(exc).__name__, str(exc)[:80])


def archive_total():
    try:
        return json.loads(fetch(UPDATES_API + "?$top=1&$count=true")).get(
            "@odata.count")
    except Exception:                                          # noqa: BLE001
        return None


def measure_rss_window(weeks=16):
    """Walk back week by week until the RSS stops agreeing with the API.

    Measured, never assumed. The AWS brief's lesson: "about two weeks" turned
    out to be exactly 12 days, and the difference decided whether an inventory
    was publishable.
    """
    try:
        rss = [d for d, _, _ in parse(fetch(UPDATES_RSS))]
    except Exception as exc:                                   # noqa: BLE001
        return None, "RSS unreadable: %s" % exc
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    out = []
    boundary = None
    for i in range(1, weeks + 1):
        a = monday - datetime.timedelta(weeks=i)
        b = a + datetime.timedelta(days=6)
        _, n, err = updates_in_range(a, b)
        if err:
            out.append((a, b, None, None))
            continue
        api_n = n or 0
        rss_n = sum(1 for d in rss if a <= d <= b)
        out.append((a, b, api_n, rss_n))
        if boundary is None and rss_n < api_n:
            boundary = a
    return (out, boundary), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start", nargs="?", help="YYYY-MM-DD (default: 7 days ago)")
    ap.add_argument("end", nargs="?", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--markdown", action="store_true",
                    help="emit a markdown table per day")
    ap.add_argument("--audit", action="store_true",
                    help="probe every source and report its health, then exit")
    ap.add_argument("--deep", action="store_true",
                    help="with --audit: re-measure the RSS divergence point")
    ap.add_argument("--msrc-all", action="store_true",
                    help="do not filter the MSRC feed to Azure products")
    args = ap.parse_args()

    if args.audit:
        results = gather()
        total = archive_total()
        today = datetime.date.today()
        wk_rows, wk_total, wk_err = updates_in_range(
            today - datetime.timedelta(days=6), today)

        print("BACKBONE — Azure Updates JSON API")
        print("  %s" % UPDATES_API)
        print("  archive holds %s records; no truncation window (range is "
              "queried, not sliced)" % (total if total is not None else "?"))
        if wk_err:
            print("  last 7 days: QUERY FAILED — %s" % wk_err)
        else:
            print("  last 7 days: %d announcements" % (wk_total or 0))
        print()

        print("%-24s %6s  %s" % ("SOURCE", "ITEMS", "COVERAGE"))
        stale_cut = today - datetime.timedelta(days=45)
        broken = 0
        for name, rows, err in results:
            if err:
                broken += 1
                print("%-24s %6s  BROKEN — %s" % (name, "-", err))
            elif not rows:
                broken += 1
                print("%-24s %6d  EMPTY FEED — wrong id or dead source"
                      % (name, 0))
            else:
                flag = "  STALE" if rows[0][0] < stale_cut else ""
                if name == MSRC_NAME:
                    az = sum(1 for r in rows if AZURE_CVE_RE.search(r[1]))
                    flag += "  (%d Azure of %d — all-Microsoft CVE feed)" % (
                        az, len(rows))
                print("%-24s %6d  %s to %s%s"
                      % (name, len(rows), rows[-1][0], rows[0][0], flag))
        for name in MANUAL_SOURCES:
            print("%-24s %6s  no feed found — check by hand" % (name[:24], "-"))

        if args.deep:
            print("\nRSS TRUNCATION — measured, week by week")
            (weeks, boundary), err = measure_rss_window()
            if err:
                print("  %s" % err)
            else:
                print("  %-25s %6s %6s  %s"
                      % ("WEEK", "API", "RSS", "verdict"))
                for a, b, api_n, rss_n in weeks:
                    if api_n is None:
                        print("  %s to %s  API query failed" % (a, b))
                        continue
                    v = ("match" if rss_n == api_n
                         else "RSS SHORT by %d" % (api_n - rss_n))
                    print("  %s to %s %6d %6d  %s" % (a, b, api_n, rss_n, v))
                if boundary:
                    print("\n  RSS is reliable back to %s (%d days); before "
                          "that it under-reports and eventually returns zero "
                          "for weeks that were not empty."
                          % (boundary, (today - boundary).days))
        print("\n%d source(s) broken or empty." % broken)
        return 1 if broken else 0

    today = datetime.date.today()
    end = datetime.date.fromisoformat(args.end) if args.end else today
    start = (datetime.date.fromisoformat(args.start) if args.start
             else end - datetime.timedelta(days=6))

    upd, upd_total, upd_err = updates_in_range(start, end)
    if upd_err:
        print("*** BACKBONE QUERY FAILED — %s" % upd_err, file=sys.stderr)
        print("Do not publish a roundup from this run: the Azure Updates "
              "archive is the inventory.", file=sys.stderr)
        return 1
    print("%-24s: %3d in range  (archive queried, no truncation)"
          % ("Azure Updates", len(upd)), file=sys.stderr)

    results = gather()
    failures = []
    inrange = {}
    for name, rows, err in results:
        if err:
            failures.append(name)
            print("%-24s: FETCH FAILED — %s" % (name, err), file=sys.stderr)
            continue
        hits = [r for r in rows if start <= r[0] <= end]
        if name == MSRC_NAME and not args.msrc_all:
            keep = [r for r in hits if AZURE_CVE_RE.search(r[1])]
            suppressed = len(hits) - len(keep)
            hits = keep
            inrange[name] = hits
            print("%-24s: %3d in range  (%d non-Azure CVEs suppressed; "
                  "feed holds %d) — --msrc-all to see them"
                  % (name, len(hits), suppressed, len(rows)), file=sys.stderr)
            continue
        inrange[name] = hits
        print("%-24s: %3d in range  (feed holds %d)"
              % (name, len(hits), len(rows)), file=sys.stderr)
    for name in MANUAL_SOURCES:
        print("%-24s: NO FEED — check by hand" % name[:24], file=sys.stderr)

    # Cross-check: the RSS twin should agree with the API inside its window.
    # Disagreement is not fatal — the API is authoritative — but it dates the
    # RSS window, which is the thing that silently moves.
    rss_hits = len(inrange.get("Azure Updates (RSS)") or [])
    if rss_hits < len(upd):
        print("\nNote: the Updates RSS reports %d for this range against the "
              "API's %d. Expected outside the RSS window; the API figure is "
              "the one to trust." % (rss_hits, len(upd)), file=sys.stderr)
    print(file=sys.stderr)

    if not upd and not any(inrange.values()):
        print("Nothing in range across any source.", file=sys.stderr)
        return 1

    by_day = collections.OrderedDict()
    for d, t, l in upd:
        by_day.setdefault(d, []).append((t, l))

    out = io.StringIO()
    if args.markdown:
        for d in sorted(by_day, reverse=True):
            out.write("\n### %s (%d)\n\n"
                      % (d.strftime("%A %d %B %Y"), len(by_day[d])))
            for t, l in by_day[d]:
                out.write("- [%s](%s)\n" % (t, l))
    else:
        out.write("%s to %s — %d announcements\n\n" % (start, end, len(upd)))
        for d in sorted(by_day, reverse=True):
            out.write("%s  (%d)\n" % (d, len(by_day[d])))
            for t, l in by_day[d]:
                out.write("   %s\n      %s\n" % (t, l))
            out.write("\n")

    for name, _ in SOURCES:
        if name == "Azure Updates (RSS)":
            continue
        hits = inrange.get(name) or []
        if not hits:
            continue
        out.write("\n%s (%d)\n" % (name, len(hits)))
        for d, t, l in hits:
            out.write("   %s  %s\n      %s\n" % (d, t, l))

    sys.stdout.buffer.write(out.getvalue().encode("utf-8"))
    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
