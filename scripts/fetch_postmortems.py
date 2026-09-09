#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collect the vendors' own post-incident write-ups for all three clouds.

    python scripts/fetch_postmortems.py            # refresh the store
    python scripts/fetch_postmortems.py --dry-run  # fetch and report only
    python scripts/fetch_postmortems.py --limit 3  # only N per cloud

Where this comes from
---------------------
Every word shown to a reader is the vendor's, quoted and linked. Nothing here
summarises an outage in my words, and nothing is written from memory -- a
plausible-sounding account of a famous incident is exactly the failure this
site is built to refuse, because a reader cannot tell a remembered detail from
a verified one.

    AWS     https://aws.amazon.com/premiumsupport/technology/pes/
            An index of ~20 post-event summaries, each its own page.
    Azure   https://azure.status.microsoft/en-us/status/history/
            Post Incident Reviews, retained five years, server-rendered with
            a tracking ID and a stable aka.ms permalink per incident.
    Google  https://status.cloud.google.com/incidents.json
            Resolved incidents carry an incident report in their updates.

Why the three are parsed differently
------------------------------------
They publish in genuinely different shapes and flattening them into one schema
would mean inventing the missing parts.

Azure writes to a fixed template -- "What happened?", "What went wrong and
why?", "How did we respond?", "How are we making incidents like this less
likely?" -- so its sections are extracted as sections.

Google writes a mini incident report with labelled fields (Root Cause,
Remediation and Prevention), so those are extracted.

AWS writes an essay with no headings at all. It is stored as prose and shown
as prose. Giving it invented section headings would imply a structure AWS did
not publish, and the difference between a vendor that publishes structured
analysis and one that does not is itself worth showing.
"""
import argparse
import datetime
import html as htmllib
import io
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "intelligence", "postmortems.json")

AWS_INDEX = "https://aws.amazon.com/premiumsupport/technology/pes/"
AZURE_HISTORY = "https://azure.status.microsoft/en-us/status/history/"
# The API behind that page's filters. The page itself renders only the
# most recent review; setting its date filter to "All" calls this, ten
# reviews to a page, back to 2024.
AZURE_API = ("https://azure.status.microsoft/en-us/statushistoryapi/"
             "?serviceSlug=all&regionSlug=all&startDate=all&page=%d"
             "&shdrefreshflag=true")
GCP_INCIDENTS = "https://status.cloud.google.com/incidents.json"

UA = "jayanthkatta.com postmortem fetcher (+https://jayanthkatta.com)"
CTX = ssl.create_default_context()


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def text(s):
    """HTML to readable prose, preserving paragraph breaks.

    Block tags become newlines BEFORE tags are stripped, otherwise every
    paragraph runs into the next and a 2,000-word summary arrives as one
    unbroken wall.
    """
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6])[^>]*>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = htmllib.unescape(s)
    s = re.sub(r"[ \t ]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip()


def parse_aws(limit=None, have=None):
    """The index gives titles and links; each summary is its own page.

    `have` is the set of URLs already in the store. AWS post-event summaries
    are immutable once published -- they describe an event that finished years
    ago -- so refetching all eighteen on every run would be eighteen HTTP
    requests an hour to re-read text that cannot have changed. Only the index
    is read every time; a detail page is fetched once, the first time it
    appears there.
    """
    have = have or set()
    idx = get(AWS_INDEX)
    seen, out = set(), []
    for href, title in re.findall(
            r'<a[^>]+href="([^"]*/message/[^"]+)"[^>]*>([^<]{8,200})</a>', idx):
        url = urllib.parse.urljoin(AWS_INDEX, href)
        title = htmllib.unescape(title).strip()
        if url in seen or not title:
            continue
        seen.add(url)
        if url in have:
            continue                      # immutable and already stored
        out.append({"url": url, "title": title})
    if limit:
        out = out[:limit]

    got = []
    for rec in out:
        try:
            raw = get(rec["url"])
        except Exception as ex:                                 # noqa: BLE001
            print("   aws  SKIP %s (%s)" % (rec["url"][-14:], str(ex)[:40]))
            continue
        # Take <main>, not the whole page. Everything outside it is aws.com
        # furniture -- global nav, a re:Invent banner, footer links -- and it
        # arrived ahead of the summary so every AWS entry opened with
        # "re:Invent 2026 The session catalog is live". Worse, the banner
        # carried a year, which the date guess below then believed.
        m = re.search(r"(?is)<main[^>]*>(.*?)</main>", raw)
        body = text(m.group(1) if m else raw)
        body = re.split(r"Return to Post-Event Summaries", body)[0].strip()
        if len(body) < 400:            # a nav-only page, not a summary
            continue
        got.append({
            "cloud": "aws",
            "id": rec["url"].rstrip("/").rsplit("/", 1)[-1],
            "title": rec["title"],
            "date": aws_date(rec["title"], body),
            "url": rec["url"],
            "body": body[:14000],
            "sections": [],           # AWS publishes no headings. See module docstring.
            "shape": "prose",
        })
        print("   aws  %-52s %5d chars" % (rec["title"][:50], len(body)))
    return got


MONTHS = ("January February March April May June July August September "
          "October November December").split()


def aws_date(title, body):
    """AWS states the date in prose, not as a field. Take it, or leave it blank.

    Guessing from a filename would produce a confident wrong date -- the
    /message/ IDs look like dates (101925, 073024) and are not reliably so.

    There is deliberately NO bare-year fallback. It used to match the first
    "20xx" anywhere in the text, which on the DynamoDB summary picked up a
    re:Invent 2026 banner and dated a October 2025 outage to 2026. A wrong
    date presented as fact is worse than a missing one, because a reader has
    no way to doubt it -- an absent date at least shows itself.
    """
    # Ordinals, and a comma after the month.
    #
    # AWS writes "December 10th, 2021" and "November, 25th 2020". The
    # pattern required "Month DD, YYYY" exactly, so the "th" ended the match
    # and eleven of eighteen summaries fell into "Undated" -- making the
    # archive look as though AWS published nothing between 2018 and 2025. It
    # published in 2017, 2020, 2021, 2023 and 2024; this could not read them.
    # The WHOLE body, not the first 2,500 characters. AWS states the date
    # early in most summaries and well down the page in others -- the Tokyo
    # Direct Connect event says "September 2, 2021" past that cut-off.
    # Verified safe before widening: it adds two dates and changes none of
    # the twelve already read, so it is not picking up a date from prose
    # about some earlier incident.
    for src in (title, body):
        m = re.search(r"\b(%s),?\s+(\d{1,2})(?:st|nd|rd|th)?"
                      r"(?:\s*(?:and|-|–|to)\s*\d{1,2}(?:st|nd|rd|th)?)?,?\s+(20\d\d)\b"
                      % "|".join(MONTHS), src)
        if m:
            return "%s-%02d-%02d" % (m.group(3), MONTHS.index(m.group(1)) + 1,
                                     int(m.group(2)))
    return ""


AZ_HEADINGS = [
    "What happened?",
    "What do we know so far?",
    "What went wrong and why?",
    "How did we respond?",
    "How are we making incidents like this less likely or less impactful?",
    "How can we make our incident communications more useful?",
]


def parse_azure(limit=None):
    """Azure writes to a fixed template, so its sections survive as sections.

    Only ONE review is on this page at a time -- Azure shows the most recent
    and retains the rest for five years behind its own navigation. So this is
    a trickle, not an archive: the store accumulates what each run sees rather
    than mirroring the page, which is why merge() below never drops anything.

    The date and title live in the toggle ANCHOR, which sits before the panel
    being split on, so they are read from the aria-controls attribute that
    links the two. Reading them from inside the panel yielded the id attribute
    as a title.
    """
    out = []
    pages = []
    # Read the API, not the page. Scraping /status/history/ returned exactly
    # ONE review -- so the write-ups section showed a single Azure entry while
    # the timeline beside it, which already used this API, carried thirty. The
    # same vendor, the same day, two different answers on one screen.
    # Page until empty. This read three pages because that was the number I
    # happened to write; Azure publishes 82 reviews across nine.
    for n in range(1, 26):
        try:
            body = get(AZURE_API % n)
        except Exception:                                       # noqa: BLE001
            break
        if "incident-history-collapse-" not in body:
            break
        pages.append(body)
    if not pages:
        pages = [get(AZURE_HISTORY)]

    for page in pages:
        # Capture the whole anchor, not one text run: the date and the title sit in
        # separate elements inside it, so a single [^<] capture stopped at the
        # first tag and yielded a bare date with no title.
        heads = {tid: text(inner) for tid, inner in re.findall(
            r'aria-controls="incident-history-collapse-([A-Z0-9-]+)"[^>]*>(.*?)</a>',
            page, re.S)}
        for tid, panel in re.findall(
                r'id="incident-history-collapse-([A-Z0-9-]+)"(.*?)(?=id="incident-history-collapse-|\Z)',
                page, re.S):
            body = text(panel)
            head = htmllib.unescape(heads.get(tid, "")).strip()
            m = re.match(r"(\d{2})/(\d{2})/(20\d\d)\s*(.*)", head)
            date = "%s-%s-%s" % (m.group(3), m.group(1), m.group(2)) if m else ""
            title = (m.group(4) if m else head).strip(" -–") or             "Post Incident Review %s" % tid

            secs = []
            for i, h in enumerate(AZ_HEADINGS):
                a = body.find(h)
                if a < 0:
                    continue
                nxt = [body.find(x, a + len(h)) for x in AZ_HEADINGS[i + 1:]]
                nxt = [x for x in nxt if x > 0]
                end = min(nxt) if nxt else min(len(body), a + 6000)
                chunk = body[a + len(h):end].strip()
                if len(chunk) > 40:
                    secs.append({"heading": h.rstrip("?"), "text": chunk[:6000]})
            if not secs:
                continue
            out.append({
                "cloud": "azure",
                "id": tid,
                "title": title[:200],
                "date": date,
                # See fetch_status.py: aka.ms/AzPIR/<id> is the feedback
            # survey, not the review.
            "url": "https://azure.status.microsoft/en-us/status/history/",
            "tracking": tid,
                "body": body[:14000],
                "sections": secs,
                "shape": "sections",
            })
            print("   az   %-52s %d section(s)" % (title[:50], len(secs)))
            if limit and len(out) >= limit:
                break
    return out


# Google writes Markdown, so the report structure is in "## Heading" lines and
# "**Field**: value" pairs -- not bare "Field:" at line start, which is what an
# earlier version looked for and why it extracted zero fields from every
# report. Some reports arrive with the markers escaped ("\#\# Summary"), so
# both forms are accepted.
GCP_HEAD = re.compile(r"(?m)^\s*(?:\\?#){1,6}\s*(.+?)\s*$")

# Headings that carry no incident detail: an apology and a caveat, identical on
# every report. Dropping them keeps the panel to what actually differs.
GCP_SKIP = ("preliminary incident report", "incident report",
            "mini incident report")


def parse_gcp(limit=None):
    """Google's resolved incidents carry an incident report in the updates."""
    data = json.loads(get(GCP_INCIDENTS))
    out = []
    for i in data:
        if not i.get("end"):
            continue
        ups = sorted(i.get("updates", []), key=lambda u: u.get("created", ""))
        report = ""
        for u in reversed(ups):
            t = u.get("text") or ""
            if re.search(r"Incident Report|Root Cause|Remediation", t, re.I):
                report = t
                break
        if not report:
            continue

        # Split on headings, keeping each heading with the prose beneath it.
        marks = list(GCP_HEAD.finditer(report))
        secs = []
        for n, m in enumerate(marks):
            # Strip the markers themselves too: an escaped report leaves
            # "## Summary" as the heading text once the backslashes go.
            head = m.group(1).replace("\\", "").lstrip("# ").strip()
            stop = marks[n + 1].start() if n + 1 < len(marks) else len(report)
            chunk = report[m.end():stop].strip()
            chunk = re.sub(r"\*\*(.+?)\*\*", r"\1", chunk)    # bold markers
            chunk = re.sub(r"\n{3,}", "\n\n", chunk).strip()
            if head.lower() in GCP_SKIP or len(chunk) < 25:
                continue
            secs.append({"heading": head[:120], "text": chunk[:6000]})

        body = re.sub(r"(?m)^\s*(?:\\?#){1,6}\s*", "", report)
        body = re.sub(r"\*\*(.+?)\*\*", r"\1", body).strip()
        out.append({
            "cloud": "gcp",
            "id": i.get("id", ""),
            "title": re.sub(r"\s+", " ", i.get("external_desc") or "").strip()[:200],
            "date": (i.get("begin") or "")[:10],
            "url": urllib.parse.urljoin("https://status.cloud.google.com/",
                                        i.get("uri") or ""),
            "body": body[:14000],
            "sections": secs,
            "shape": "sections" if secs else "prose",
            "severity": i.get("severity", ""),
            # Keep the count even when the list is trimmed. Two Google
            # incidents affect 27 products; showing ten and saying nothing
            # understates the blast radius by more than half.
            "products": [p.get("title") for p in i.get("affected_products", [])][:10],
            "product_count": len(i.get("affected_products") or []),
        })
        print("   gcp  %-52s %d section(s)" % (out[-1]["title"][:50], len(secs)))
        if limit and len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(io.open(OUT, encoding="utf-8"))
        except ValueError:
            prev = {}
    prev_items = {r["cloud"] + ":" + r["id"]: r
                  for r in (prev.get("postmortems") or [])}

    items, sources = [], {}
    known_urls = {r.get("url") for r in prev_items.values() if r.get("url")}

    for cloud, fn, label, src in (
            ("aws", parse_aws, "AWS post-event summaries", AWS_INDEX),
            ("azure", parse_azure, "Azure Post Incident Reviews", AZURE_HISTORY),
            ("gcp", parse_gcp, "Google Cloud incident reports", GCP_INCIDENTS)):
        try:
            got = (fn(args.limit, known_urls) if cloud == "aws"
                   else fn(args.limit))
            items += got
            sources[cloud] = {"name": label, "url": src, "ok": True,
                              "count": len(got), "fetched": stamp()}
        except Exception as ex:                                 # noqa: BLE001
            # Same rule as the status fetcher: a failed fetch keeps what was
            # known rather than silently publishing a shorter list, because a
            # missing outage looks exactly like an outage that never happened.
            keep = [v for k, v in prev_items.items() if k.startswith(cloud + ":")]
            items += keep
            sources[cloud] = {"name": label, "url": src, "ok": False,
                              "error": str(ex)[:200], "count": len(keep),
                              "fetched": (prev.get("sources", {}).get(cloud, {})
                                          or {}).get("fetched", "")}
            print("   %-4s FETCH FAILED: %s (kept %d)" % (cloud, str(ex)[:50], len(keep)))

    # Accumulate, never mirror. Azure shows ONE review on its history page at a
    # time and Google's feed rolls incidents off, so a fetch is a glimpse of a
    # moving window rather than the archive. Replacing the store with each
    # fetch would silently delete write-ups that are still perfectly valid and
    # still linkable -- the record would shrink every time a vendor moved on.
    merged = dict(prev_items)
    for r in items:
        merged[r["cloud"] + ":" + r["id"]] = r
    kept = len(merged) - len(items)
    items = list(merged.values())
    if kept > 0:
        print("  kept %d write-up(s) from earlier runs" % kept)

    # Report what is HELD, not what was just downloaded. With the incremental
    # AWS fetch a steady state means zero new pages, and a count of "0" next to
    # a source that holds eighteen write-ups reads as a broken feed.
    for cloud in sources:
        sources[cloud]["count"] = sum(1 for r in items if r.get("cloud") == cloud)
        sources[cloud]["new"] = sum(1 for r in items
                                    if r.get("cloud") == cloud
                                    and (cloud + ":" + r.get("id", "")) not in prev_items)

    items.sort(key=lambda r: (r.get("date") or ""), reverse=True)
    payload = {"updated": stamp(), "sources": sources, "postmortems": items}

    print()
    for c in ("aws", "azure", "gcp"):
        s = sources[c]
        print("  %-6s %2d write-up(s)  %s" % (c, s["count"],
                                              "ok" if s["ok"] else "FAILED"))

    if args.dry_run:
        print("  dry run: nothing written")
        return 0

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, OUT)
    print("  -> %s" % OUT)
    return 0 if any(s["ok"] for s in sources.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
