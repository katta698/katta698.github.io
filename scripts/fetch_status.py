#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch live incident status from all three clouds' own status feeds.

    python scripts/fetch_status.py             # write intelligence/status.json
    python scripts/fetch_status.py --stdout    # print, write nothing
    python scripts/fetch_status.py --dry-run   # fetch and report, write nothing

Why a scheduled fetch and not a browser one
-------------------------------------------
Only Google sends Access-Control-Allow-Origin. Measured 2026-09-08:

    GCP    Access-Control-Allow-Origin: *
    AWS    (none)
    Azure  (none)

A page cannot read the other two directly, so all three are fetched
server-side on a schedule and committed, in the same shape as the announcement
store. The cost is that the page is only as current as the last run, which is
why every source carries its own fetch timestamp and the page shows it.

The failure that matters
------------------------
An unreachable status feed and a cloud with no incidents produce the same
thing: an empty list. Rendering both as "Operational" turns a monitoring
failure into false reassurance, which is worse than showing nothing -- a
reader would take a green tick from a fetch that never completed.

So every source records its own outcome, and "ok: false" is a distinct state
the page must render differently from "no incidents". A source that fails also
KEEPS its previous incidents rather than dropping to empty, because the last
known truth is closer to reality than a blank.

What is deliberately not here
-----------------------------
An ETA. None of the three publishes one as structured data. They sometimes
write "we expect recovery within the hour" inside an update, and lifting that
into a field the page presents as an ETA would manufacture a commitment the
vendor never made. Elapsed time and their own words are shown instead.
"""
import argparse
import datetime
import io
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "intelligence", "status.json")
HISTORY = os.path.join(ROOT, "intelligence", "status-history.json")

SOURCES = {
    "aws":   ("AWS Health Dashboard", "https://status.aws.amazon.com/data.json"),
    "azure": ("Azure Status",         "https://azure.status.microsoft/en-us/status/feed/"),
    "gcp":   ("Google Cloud Status",  "https://status.cloud.google.com/incidents.json"),
}

UA = "jayanthkatta.com status fetcher (+https://jayanthkatta.com)"
CTX = ssl.create_default_context()


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def stamp(dt=None):
    return (dt or now()).isoformat(timespec="seconds").replace("+00:00", "Z")


def get(url, timeout=45):
    """Return (bytes, http_status). Raises on anything that is not a response."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read(), r.status


def flat(s, limit=500):
    """Collapse whitespace and strip Markdown headings.

    Google writes its updates in Markdown, so an update opens with
    "## Preliminary Incident Report" and renders that literally in HTML that
    does not process Markdown. Only the heading markers are removed -- the
    prose is the vendor's and is shown as written.
    """
    s = re.sub(r"^#{1,6}\s*", "", (s or "").strip(), flags=re.M)
    return re.sub(r"\s+", " ", s).strip()[:limit]


def parse_gcp(raw):
    data = json.loads(raw.decode("utf-8"))
    live, past = [], []
    for i in data:
        ups = sorted(i.get("updates", []), key=lambda u: u.get("created", ""))
        locs = (i.get("currently_affected_locations") or []) + \
               (i.get("previously_affected_locations") or [])
        rec = {
            "id": i.get("id", ""),
            "title": flat(i.get("external_desc"), 240),
            "severity": i.get("severity", ""),
            "impact": i.get("status_impact", ""),
            "begin": i.get("begin", ""),
            "end": i.get("end") or "",
            "products": [p.get("title") for p in i.get("affected_products", [])][:10],
            "regions": sorted({l.get("id") for l in locs if l.get("id")})[:12],
            "update": flat((i.get("most_recent_update") or {}).get("text")),
            "updates": len(ups),
            # Google is the only one of the three that publishes an incident
            # start distinct from its first public update, so it is the only
            # one where "how long before they said anything" is a real number.
            "first_update": ups[0].get("created", "") if ups else "",
            "url": "https://status.cloud.google.com" + (i.get("uri") or ""),
        }
        (past if rec["end"] else live).append(rec)
    return live, past


def parse_aws(raw):
    """data.json is UTF-16 with a BOM.

    Decoding it as UTF-8 gives a string with a NUL between every character,
    and json.loads then fails with a message about an unexpected token that
    reads like the endpoint changed shape rather than like an encoding bug.
    """
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    data = json.loads(raw.decode(enc, "replace"))
    items = data if isinstance(data, list) else (data.get("current") or [])
    live = []
    for i in items:
        log = sorted(i.get("event_log") or [], key=lambda x: x.get("timestamp", 0))
        live.append({
            "id": i.get("arn", ""),
            "title": flat(i.get("summary"), 240),
            "service": i.get("service_name", ""),
            "region": i.get("region_name", ""),
            "begin": str(i.get("date", "")),
            "update": flat(log[-1].get("message") if log else ""),
            "updates": len(log),
            # No first_update: AWS's "date" IS its first announcement, so the
            # gap is structurally zero and reporting it would flatter AWS for
            # disclosing less. See the transparency note on the page.
            "url": "https://health.aws.amazon.com/health/status",
        })
    return live, []


def parse_azure(raw):
    """Azure's feed carries items only while something is wrong.

    An empty feed is therefore the healthy state, not a failed fetch -- which
    is exactly why the fetch outcome is recorded separately from the item
    count. Without that, "Azure is fine" and "we could not reach Azure" are
    indistinguishable.
    """
    body = raw.decode("utf-8", "replace")
    live = []
    for it in re.findall(r"<item[ >].*?</item>", body, re.S):
        t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
        d = re.search(r"<pubDate>([^<]+)<", it)
        c = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", it, re.S)
        live.append({
            "id": flat(t.group(1) if t else "", 80),
            "title": flat(t.group(1) if t else "", 240),
            "begin": (d.group(1) if d else ""),
            "update": flat(re.sub(r"<[^>]+>", " ", c.group(1)) if c else ""),
            "updates": 1,
            "url": "https://azure.status.microsoft/en-us/status",
        })
    return live, []


PARSERS = {"aws": parse_aws, "azure": parse_azure, "gcp": parse_gcp}


def load_previous():
    if not os.path.exists(OUT):
        return {}
    try:
        return json.load(io.open(OUT, encoding="utf-8"))
    except ValueError:
        return {}


def merge_history(past_by_cloud):
    """Keep resolved incidents so the track-record panel has something to say.

    Google's feed only carries recent incidents, so anything not captured
    before it rolls off is gone. Appending here means the record grows from
    the day this starts running rather than being limited to whatever the
    feed happens to hold.
    """
    hist = {}
    if os.path.exists(HISTORY):
        try:
            hist = json.load(io.open(HISTORY, encoding="utf-8"))
        except ValueError:
            hist = {}
    items = hist.get("incidents") or {}
    added = 0
    for cloud, rows in past_by_cloud.items():
        for r in rows:
            key = "%s:%s" % (cloud, r.get("id") or r.get("title", "")[:60])
            if key not in items:
                items[key] = dict(r, cloud=cloud)
                added += 1
    hist["incidents"] = items
    hist["updated"] = stamp()
    tmp = HISTORY + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(hist, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, HISTORY)
    return added, len(items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    prev = load_previous()
    prev_clouds = prev.get("clouds") or {}

    clouds, sources, past = {}, {}, {}
    for cloud, (label, url) in SOURCES.items():
        started = now()
        try:
            raw, code = get(url)
            live, resolved = PARSERS[cloud](raw)
            clouds[cloud] = live
            past[cloud] = resolved
            sources[cloud] = {
                "name": label, "url": url, "ok": True, "http": code,
                "fetched": stamp(), "ms": int((now() - started).total_seconds() * 1000),
                "bytes": len(raw),
            }
        except Exception as exc:                                # noqa: BLE001
            # Keep whatever was last known rather than dropping to empty. An
            # empty list renders as "no incidents", and a fetch failure must
            # never be shown as good news.
            clouds[cloud] = prev_clouds.get(cloud, [])
            past[cloud] = []
            sources[cloud] = {
                "name": label, "url": url, "ok": False, "http": None,
                "fetched": (prev.get("sources", {}).get(cloud, {}) or {}).get("fetched", ""),
                "error": str(exc)[:200], "attempted": stamp(),
            }

    added, total = (0, 0) if args.dry_run else merge_history(past)

    payload = {
        "checked": stamp(),
        "clouds": clouds,
        "sources": sources,
        "history_count": total,
    }

    if args.stdout:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0

    for c in ("aws", "azure", "gcp"):
        s = sources[c]
        if s["ok"]:
            print("  %-6s %d active  (HTTP %s, %d ms, %d bytes)"
                  % (c, len(clouds[c]), s["http"], s["ms"], s["bytes"]))
        else:
            print("  %-6s FETCH FAILED: %s  (showing %d from %s)"
                  % (c, s["error"], len(clouds[c]), s["fetched"] or "never"))
    if not args.dry_run:
        print("  history: +%d resolved, %d total" % (added, total))

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

    # A run where every source failed is worth a non-zero exit so the workflow
    # shows red. One source failing is normal weather and must not.
    return 1 if not any(s["ok"] for s in sources.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
