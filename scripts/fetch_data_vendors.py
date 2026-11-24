#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch what the data platforms actually shipped, into data/releases.json.

    python scripts/fetch_data_vendors.py            # fetch and write
    python scripts/fetch_data_vendors.py --audit    # probe every feed, write nothing

The three clouds are already covered by the announcement store. This is the
layer the store cannot see: the engines and the independent vendors.

WHY RELEASE FEEDS RATHER THAN BLOGS
-----------------------------------
A release tag is a fact with a date. A blog post is marketing with a date.
Where a project publishes releases, this reads releases -- so "Iceberg
shipped 1.12.0 on 2026-09-30" is checkable against the tag, and nothing here
depends on how a vendor chose to describe its own quarter.

Three vendors have no machine-readable feed and the page must say so rather
than quietly omit them:

  Snowflake   www.snowflake.com/en/blog/feed/ answers 403 to any agent, and
              docs.snowflake.com publishes release notes as HTML only.
  Confluent   /blog/feed/ and /blog/rss.xml are both 404. The ksql repo's
              tags are CI builds (v8.5.0-592), not product releases.
  Databricks  no release feed; the blog feed is carried here instead, and is
              labelled as a blog, because it is one.

Measured 2026-11-22. Re-run --audit before trusting a quiet week: a feed that
dies answers 200 with an empty list, which looks exactly like a slow month.

PRE-RELEASES ARE NOT RELEASES
-----------------------------
Spark, Flink and Kafka tag every release candidate, and Delta Lake's feed is
dominated by Databricks Runtime build tags (dbr-20261106-ae8430c6f). Counting
those would make a project's cadence a function of how publicly it tests.
RELEASE_RE keeps tags that look like a shipped version and nothing else.
"""
import datetime
import io
import json
import os
import re
import ssl
import sys
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "releases.json")
UA = ("jayanthkatta.com data-platform research; contact "
      "katta.jayant@gmail.com")

ATOM = {"a": "http://www.w3.org/2005/Atom"}

# kind: "release" is a tagged version; "blog" is a post and is labelled as one.
# layer maps onto the lifecycle the page is built around.
SOURCES = [
    # name, layer, kind, url
    ("Apache Iceberg",    "store",     "release",
     "https://github.com/apache/iceberg/releases.atom"),
    ("Delta Lake",        "store",     "release",
     "https://github.com/delta-io/delta/releases.atom"),
    ("Apache Hudi",       "store",     "release",
     "https://github.com/apache/hudi/releases.atom"),
    ("DuckDB",            "store",     "release",
     "https://github.com/duckdb/duckdb/releases.atom"),
    ("Apache Spark",      "transform", "release",
     "https://github.com/apache/spark/releases.atom"),
    ("Apache Airflow",    "transform", "release",
     "https://github.com/apache/airflow/releases.atom"),
    ("dbt Core",          "transform", "release",
     "https://github.com/dbt-labs/dbt-core/releases.atom"),
    ("Apache Kafka",      "ingest",    "release",
     "https://github.com/apache/kafka/releases.atom"),
    ("Apache Flink",      "ingest",    "release",
     "https://github.com/apache/flink/releases.atom"),
    ("Trino",             "serve",     "release",
     "https://github.com/trinodb/trino/releases.atom"),
    ("Great Expectations", "govern",   "release",
     "https://github.com/great-expectations/great_expectations/releases.atom"),
    ("Databricks",        "transform", "blog",
     "https://www.databricks.com/feed"),
    ("MongoDB",           "store",     "blog",
     "https://www.mongodb.com/blog/rss"),
    ("Elastic",           "serve",     "blog",
     "https://www.elastic.co/blog/feed"),
]

# Vendors with no machine-readable feed. Printed on the page as a gap rather
# than left out, because a missing vendor reads as a vendor doing nothing.
NO_FEED = [
    ("Snowflake", "blog feed answers 403; release notes are HTML only"),
    ("Confluent", "blog feed is 404; the public tags are CI builds"),
]

# A shipped version: 1.12.0, v3.5.10, 484, 1.1.2 Release, airflow/2.9.1.
# Rejects rc/beta/alpha/preview/nightly and Databricks Runtime build tags.
RELEASE_RE = re.compile(
    r"(?:^|[\s/v-])(\d+\.\d+(?:\.\d+)?|\d{3,4})(?:\s|$|[^\d.])", re.I)
PRERELEASE_RE = re.compile(r"rc\d|alpha|beta|preview|nightly|snapshot|-dbr|^dbr-",
                           re.I)


def get(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = None
    for _ in range(tries):
        try:
            return urllib.request.urlopen(
                req, timeout=60, context=ssl.create_default_context()).read()
        except Exception as e:          # noqa: BLE001 - reported, not raised
            last = e
    raise last


def _text(el, *names):
    for n in names:
        x = el.find(n, ATOM) if n.startswith("a:") else el.find(n)
        if x is not None and (x.text or "").strip():
            return x.text.strip()
    return ""


def _date(raw):
    """Atom gives ISO; RSS gives RFC 822. Return YYYY-MM-DD or ''."""
    if not raw:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%d %b %Y %H:%M:%S %z"):
        try:
            return datetime.datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    m = re.search(r"(\d{1,2}\s+\w{3}\s+\d{4})", raw)
    if m:
        try:
            return datetime.datetime.strptime(m.group(1), "%d %b %Y").date().isoformat()
        except ValueError:
            pass
    return ""


def _link(el):
    x = el.find("a:link", ATOM)
    if x is not None and x.get("href"):
        return x.get("href")
    x = el.find("link")
    if x is not None:
        return (x.text or x.get("href") or "").strip()
    return ""


def is_component_tag(title, vendor):
    """True when the tag belongs to a SUB-PROJECT, not the project itself.

    Airflow tags its CLI as `airflow-ctl/0.1.6` and its provider packages as
    `providers-amazon/...`. Counted as Airflow releases, a monorepo's cadence
    becomes a function of how many components it ships separately, and the
    engines table compares that against projects that tag once.

    Containment is not enough: "airflow-ctl" contains "airflow". The prefix
    has to BE the project token, not merely include it.
    """
    if "/" not in title:
        return False
    prefix = title.split("/", 1)[0].strip().lower()
    token = vendor.lower().replace("apache ", "").replace(" ", "")
    return prefix.replace("-", "").replace("_", "") != token


def parse(name, layer, kind, body):
    root = ET.fromstring(body)
    entries = root.findall(".//a:entry", ATOM) or root.findall(".//item")
    out = []
    for e in entries:
        title = _text(e, "a:title", "title")
        if not title:
            continue
        date = _date(_text(e, "a:updated", "a:published", "pubDate",
                           "{http://purl.org/dc/elements/1.1/}date"))
        if kind == "release":
            if PRERELEASE_RE.search(title) or not RELEASE_RE.search(title):
                continue
            if is_component_tag(title, name):
                continue
        out.append({"vendor": name, "layer": layer, "kind": kind,
                    "title": re.sub(r"\s+", " ", title)[:160],
                    "date": date, "url": _link(e)})
    return out


def fetch_all(audit=False):
    rows, report = [], []
    for name, layer, kind, url in SOURCES:
        try:
            body = get(url)
        except Exception as e:          # noqa: BLE001
            report.append((name, url, "FETCH FAILED: %s" % str(e)[:60], 0, "", ""))
            continue
        try:
            got = parse(name, layer, kind, body)
        except Exception as e:          # noqa: BLE001
            report.append((name, url, "PARSE FAILED: %s" % str(e)[:60], 0, "", ""))
            continue
        dates = sorted(d["date"] for d in got if d["date"])
        report.append((name, url, "ok", len(got),
                       dates[0] if dates else "", dates[-1] if dates else ""))
        rows.extend(got)
    return rows, report


def canary():
    """A parser that cannot fail is worse than no parser.

    Feeds the two shapes this module has to get right -- an Atom release
    entry and an RSS blog item -- and asserts the pre-release filter keeps
    the real version and drops the candidate and the runtime build tag.
    """
    atom = ("<feed xmlns='http://www.w3.org/2005/Atom'>"
            "<entry><title>apache-iceberg-1.12.0</title>"
            "<updated>2026-09-30T10:00:00Z</updated>"
            "<link href='https://example.invalid/a'/></entry>"
            "<entry><title>v3.5.10-rc1</title>"
            "<updated>2026-10-12T10:00:00Z</updated>"
            "<link href='https://example.invalid/b'/></entry>"
            "<entry><title>dbr-20261106-ae8430c6f</title>"
            "<updated>2026-11-06T10:00:00Z</updated>"
            "<link href='https://example.invalid/c'/></entry></feed>")
    got = parse("X", "store", "release", atom.encode())
    assert len(got) == 1, "pre-release filter: expected 1, got %d" % len(got)
    assert got[0]["date"] == "2026-09-30", got[0]["date"]

    rss = ("<rss><channel><item><title>Something shipped</title>"
           "<pubDate>Thu, 20 Nov 2026 09:00:00 +0000</pubDate>"
           "<link>https://example.invalid/d</link></item></channel></rss>")
    got = parse("Y", "store", "blog", rss.encode())
    assert len(got) == 1 and got[0]["date"] == "2026-11-20", got

    assert is_component_tag("airflow-ctl/0.1.6", "Apache Airflow"),         "a sub-project tag must not count as a project release"
    assert is_component_tag("providers-amazon/9.1.0", "Apache Airflow")
    assert not is_component_tag("airflow/3.1.2", "Apache Airflow")
    assert not is_component_tag("v1.12.0", "Apache Iceberg")
    return True


def main():
    canary()
    audit = "--audit" in sys.argv
    rows, report = fetch_all(audit)

    print("%-20s %7s  %-10s %-10s %s" % ("SOURCE", "ITEMS", "OLDEST",
                                         "NEWEST", "STATUS"))
    stale, dead = [], []
    today = datetime.date.today()
    for name, url, status, n, old, new in report:
        print("%-20s %7d  %-10s %-10s %s" % (name, n, old or "-", new or "-",
                                             status))
        if status != "ok":
            dead.append(name)
        elif new:
            age = (today - datetime.date.fromisoformat(new)).days
            if age > 180:
                stale.append("%s (%d days)" % (name, age))
    if dead:
        print("\nFAILED: %s" % ", ".join(dead))
    if stale:
        print("\nQUIET over 180 days: %s" % ", ".join(stale))
    for name, why in NO_FEED:
        print("NO FEED  %-12s %s" % (name, why))

    if audit:
        return 1 if dead else 0

    # Assert the run happened, rather than that the data looks plausible.
    # A fetcher that silently returns nothing looks exactly like a quiet week.
    if not rows:
        print("\nREFUSING TO WRITE: every source returned nothing.")
        return 1
    if len(dead) > len(SOURCES) // 2:
        print("\nREFUSING TO WRITE: %d of %d sources failed."
              % (len(dead), len(SOURCES)))
        return 1

    # MERGE, never overwrite. Every feed here is a rolling window of about ten
    # items, so a weekly run that replaced the file would hold ten weeks of
    # history at best and would silently shorten it the week a project shipped
    # eleven times. Keyed on vendor + title + date; re-running is a no-op.
    held = {}
    if os.path.exists(OUT):
        try:
            with io.open(OUT, encoding="utf-8") as f:
                for r in json.load(f).get("releases", []):
                    held[(r["vendor"], r["title"], r["date"])] = r
        except (ValueError, KeyError):
            pass            # a corrupt file is replaced, not merged into
    # Re-apply today's rules to what is already held. Merging only ever
    # adds, which is right for history and wrong for a record that should
    # never have been stored: when the component-tag filter arrived, the
    # airflow-ctl tag it was written to reject was already in the file and
    # would have outlived the fix. The filter is the contract; held rows obey
    # it too.
    dropped = [k for k, r in held.items()
               if r.get("kind") == "release"
               and (PRERELEASE_RE.search(r["title"])
                    or not RELEASE_RE.search(r["title"])
                    or is_component_tag(r["title"], r["vendor"]))]
    for k in dropped:
        del held[k]
    if dropped:
        print("dropped %d held row(s) the current rules reject: %s"
              % (len(dropped), ", ".join(k[1][:28] for k in dropped[:4])))

    before = len(held)
    for r in rows:
        held.setdefault((r["vendor"], r["title"], r["date"]), r)
    rows = sorted(held.values(), key=lambda r: (r["date"], r["vendor"]),
                  reverse=True)
    print("\nheld %d, %d new this run" % (before, len(rows) - before))

    payload = {
        "generated": datetime.datetime.now(datetime.timezone.utc)
                     .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [{"vendor": n, "url": u, "status": s, "items": c,
                     "newest": new} for n, u, s, c, _, new in report],
        "no_feed": [{"vendor": n, "why": w} for n, w in NO_FEED],
        "releases": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("\nwrote %s -- %d items from %d sources"
          % (os.path.relpath(OUT, ROOT), len(rows),
             sum(1 for r in report if r[2] == "ok")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
