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
import gzip
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
OUT = os.path.join(ROOT, "intelligence", "status.json")
HISTORY = os.path.join(ROOT, "intelligence", "status-history.json")
RUNS = os.path.join(ROOT, "intelligence", "status-runs.json")

SOURCES = {
    "aws":   ("AWS Health Dashboard", "https://status.aws.amazon.com/data.json"),
    "azure": ("Azure Status",         "https://azure.status.microsoft/en-us/status/feed/"),
    "gcp":   ("Google Cloud Status",  "https://status.cloud.google.com/incidents.json"),
}

GCP_BASE = "https://status.cloud.google.com/"

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
            # urljoin, not "+". Google's uri has NO leading slash
            # ("incidents/J5ia..."), so concatenation produced
            # "status.cloud.google.comincidents/J5ia..." -- a host that does
            # not resolve, on every Google incident link the page drew. It
            # looks right at a glance in both the code and the JSON, which is
            # why it survived: the string only breaks at the one character
            # where two correct halves meet.
            "url": urllib.parse.urljoin(GCP_BASE, i.get("uri") or ""),
        }
        (past if rec["end"] else live).append(rec)
    return live, past


AWS_HISTORY = ("https://history-events-us-east-1-prod.s3.amazonaws.com/"
               "historyevents.json")


def parse_aws_history(raw):
    """AWS's RESOLVED incidents, which data.json does not carry.

    This closes the biggest hole in the page. data.json lists only what is
    open right now, so every AWS incident that started and finished left no
    trace anywhere -- the store held zero resolved AWS incidents, the timeline
    could only ever show the two Middle East events still open since March,
    and a reader asking "was there an AWS outage in July?" got silence that
    looked like a no.

    The feed was found by loading health.aws.amazon.com/health/status in a
    real browser and watching what the "Service history" tab fetches. It is
    not linked or documented anywhere I could find, which is why three
    separate searches of AWS's published surfaces missed it, and why I told
    the owner of this site that AWS published no such thing. It does.

    Two things about the format.

    It is gzip, served from S3 without content negotiation, so urllib hands
    back bytes starting \\x1f\\x8b and json.loads fails with a message about
    line 1 column 1 that reads like the endpoint moved.

    And it is a dict keyed by "service-region" -- "ec2-eu-west-2",
    "multipleservices-us-west-2" -- each holding a list of events, rather than
    the flat array data.json uses. The key is the only place the region
    appears, so it is split rather than dropped: without it every historical
    incident would render with no location while the live ones show one.
    """
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    data = json.loads(raw.decode("utf-8", "replace"))
    out = []
    for key, events in (data or {}).items():
        # "multipleservices-us-west-2" -> service "multipleservices",
        # region "us-west-2". Services and regions both contain hyphens, so
        # the split is anchored on the region shape rather than on position.
        m = re.search(r"-((?:[a-z]{2}|us|eu|ap|sa|ca|me|af|il)-[a-z]+-\d+)$", key)
        region = m.group(1) if m else ""
        service = key[: m.start()] if m else key
        for e in events or []:
            log = sorted(e.get("event_log") or [],
                         key=lambda x: x.get("timestamp", 0))
            begin = e.get("date")
            # The last log entry is the resolution, so its timestamp is the
            # end. Falling back to the start would render every resolved
            # incident as lasting zero minutes.
            end = log[-1].get("timestamp") if log else None
            out.append({
                "cloud": "aws",
                "id": e.get("arn", "") or ("%s:%s" % (key, begin)),
                "title": flat(e.get("summary"), 240),
                "service": ", ".join(e.get("impacted_services") or [])[:120] or service,
                "region": region,
                "region_code": region,
                "begin": str(begin or ""),
                "end": str(end or ""),
                "update": prefer_english(flat(log[-1].get("message") if log else "", 4000))[:900],
                "updates": len(log),
                "url": "https://health.aws.amazon.com/health/status",
            })
    return out


CJK = re.compile(r"[　-鿿＀-￯]")


def prefer_english(text):
    """AWS posts Japan-region updates in Japanese AND English, in that order.

    The full string is both languages back to back, so a reader of the English
    site got a wall of Japanese with the English truncated mid-sentence
    underneath it. Neither half is wrong -- the page just showed the wrong one
    first and then cut the other off.

    The split is on the language itself rather than on a separator, because
    there is no reliable separator: the two halves are divided by a newline
    that whitespace-collapsing has already eaten by the time this runs. Any
    segment more than a fifth CJK is dropped; if that leaves nothing, the
    original is returned rather than an empty string, because a vendor writing
    only in Japanese is still the vendor speaking.
    """
    if not text or not CJK.search(text):
        return text
    parts = [p.strip() for p in re.split(r"(?<=[.。])\s+|\s*\|\s*", text) if p.strip()]
    keep = [p for p in parts if len(CJK.findall(p)) / max(len(p), 1) < 0.2]
    return " ".join(keep) if keep else text


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
        # The real region code, taken from the ARN.
        #
        # region_name is a place name -- "UAE", "Bahrain" -- while Google
        # publishes machine IDs like us-central1. Rendered side by side in the
        # region grid the two look like the same kind of label and are not, and
        # "UAE" cannot be matched against anything a reader has in a Terraform
        # file. The code is sitting in the ARN:
        #
        #   arn:aws:health:me-central-1::event/MULTIPLE_SERVICES/...
        #
        # The place name is kept separately, because it is the friendlier thing
        # to show on the incident card itself.
        arn = i.get("arn", "") or ""
        parts = arn.split(":")
        code = parts[3] if len(parts) > 3 and parts[3] else ""
        live.append({
            "id": arn,
            "title": flat(i.get("summary"), 240),
            "service": i.get("service_name", ""),
            "region": i.get("region_name", ""),
            "region_code": code,
            "begin": str(i.get("date", "")),
            "update": prefer_english(flat(log[-1].get("message") if log else "", 4000))[:900],
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
    # When this store began. Before it, a resolved incident on a feed that
    # publishes only OPEN ones left no trace anywhere, so those days are
    # genuinely unknown rather than clear. The timeline needs to draw that
    # difference, and it cannot without knowing where the record starts.
    hist.setdefault("since", stamp())
    added = 0
    for cloud, rows in past_by_cloud.items():
        for r in rows:
            key = "%s:%s" % (cloud, r.get("id") or r.get("title", "")[:60])
            if key not in items:
                items[key] = dict(r, cloud=cloud)
                added += 1
            else:
                # Refresh rather than freeze. The first version seen is not
                # the best one: an incident's text is edited after the fact,
                # and a parser fix -- picking English out of a bilingual AWS
                # update, say -- can only reach records it is allowed to
                # rewrite. Keeping the first copy forever meant every stored
                # incident was stuck with whatever the parser did on the day
                # it was captured.
                items[key].update(dict(r, cloud=cloud))
    hist["incidents"] = items
    hist["updated"] = stamp()
    # The oldest incident Google's feed still carries. Days before it are
    # outside what any run could have seen, however long this has been running.
    begins = sorted(v.get("begin", "") for v in items.values()
                    if v.get("cloud") == "gcp" and v.get("begin"))
    if begins:
        hist["gcp_horizon"] = begins[0]
    tmp = HISTORY + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(hist, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, HISTORY)
    return added, len(items)


def record_run(sources):
    """Append this run to a public log, so the page can prove its own cadence.

    The page used to claim "refreshed every 15 minutes" while the schedule had
    never fired once -- a promise with nothing behind it, which nobody could
    check without reading the Actions tab of a repo they do not own. A claim
    about freshness that a reader cannot verify is just a nicer-sounding
    version of "trust me", and this whole page exists to avoid that.

    So every run writes down when it happened and whether each source
    answered. The page then reports the cadence it ACTUALLY achieved over the
    last 24 hours instead of the one that was hoped for. If the scheduler dies
    again the number falls on its own, visibly, with no one needing to notice.

    Capped at 400 entries -- about two weeks of hourly runs -- because this is
    committed on every refresh and an unbounded log would grow forever.
    """
    log = {"runs": []}
    if os.path.exists(RUNS):
        try:
            log = json.load(io.open(RUNS, encoding="utf-8")) or {"runs": []}
        except ValueError:
            log = {"runs": []}
    runs = log.get("runs") or []
    runs.append({
        "at": stamp(),
        "ok": [c for c in sorted(sources) if sources[c].get("ok")],
        "failed": [c for c in sorted(sources) if not sources[c].get("ok")],
    })
    log["runs"] = runs[-400:]
    tmp = RUNS + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, RUNS)


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

    # AWS resolved incidents, from the history feed behind the Health
    # Dashboard's "Service history" tab. Kept out of SOURCES because it is not
    # a live status feed -- a failure here means the archive did not grow, not
    # that AWS's current state is unknown, and the two must not be reported
    # the same way.
    try:
        hraw, _ = get(AWS_HISTORY)
        hist_aws = parse_aws_history(hraw)
        past["aws"] = (past.get("aws") or []) + hist_aws
        sources["aws_history"] = {
            "name": "AWS service history", "url": AWS_HISTORY, "ok": True,
            "count": len(hist_aws), "fetched": stamp(),
        }
    except Exception as exc:                                    # noqa: BLE001
        sources["aws_history"] = {
            "name": "AWS service history", "url": AWS_HISTORY, "ok": False,
            "error": str(exc)[:200], "attempted": stamp(),
        }
        print("  aws-hist FETCH FAILED: %s" % str(exc)[:60])

    added, total = (0, 0) if args.dry_run else merge_history(past)
    if not args.dry_run:
        record_run(sources)

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
