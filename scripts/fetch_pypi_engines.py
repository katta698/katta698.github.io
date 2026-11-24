#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Client-library downloads for the data engines, into data/pypi.json.

    python scripts/fetch_pypi_engines.py
    python scripts/fetch_pypi_engines.py --audit    # probe only, write nothing

WHY THIS IS HERE AT ALL
-----------------------
Every other number on /data/ measures what a vendor SAID. Cloud announcement
feeds, release notes, SEC filings -- all of it is the supply side talking.
This is the only figure on the page that moves when somebody who is not
selling anything types `pip install`.

It is worth having precisely because it disagrees sometimes. Where the cloud
feeds and this point the same way, the conclusion is stronger than either on
its own; where they diverge, that is the interesting part and the page should
show both rather than pick.

WHAT IT IS NOT
--------------
A download is not a user, an install is not a deployment, and neither is
revenue. These counts are inflated by CI: every pipeline that reinstalls on
each run adds to them, and a project with a popular GitHub Action will look
larger than one without. They measure developer REACH, which is a real thing
and is not adoption.

They also only count PyPI. An engine used mostly from Java, SQL or a managed
console is undercounted here by construction -- Trino's Python client is not
Trino. Each row therefore names the package, not the product.

WHY NOT BIGQUERY
----------------
bigquery-public-data.pypi.file_downloads is the canonical source and needs a
GCP project, credentials and query billing. pypistats.org answers the same
question for these packages over the last 30 days with no account at all, and
a source that needs no secret is a source that cannot break when a secret
expires. Measured 2026-11-24: 8 of 8 packages resolve.
"""
import datetime
import io
import json
import os
import ssl
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "pypi.json")
UA = ("jayanthkatta.com data-platform research; contact "
      "katta.jayant@gmail.com")
API = "https://pypistats.org/api/packages/%s/recent"

# package, what it is a client for, which lifecycle stage it sits in
PACKAGES = [
    ("duckdb", "DuckDB", "the engine itself, in process", "serve"),
    ("polars", "Polars", "the engine itself, in process", "transform"),
    ("pyspark", "PySpark", "the Spark client and local runtime", "transform"),
    ("pyiceberg", "PyIceberg", "Iceberg tables from Python", "store"),
    ("dbt-core", "dbt Core", "the transformation runner", "transform"),
    ("trino", "Trino client", "a client, not the engine", "serve"),
    ("deltalake", "delta-rs", "Delta tables from Python", "store"),
    ("apache-airflow", "Apache Airflow", "the scheduler itself", "transform"),
]


def get(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = None
    for _ in range(tries):
        try:
            return urllib.request.urlopen(
                req, timeout=45, context=ssl.create_default_context()).read()
        except Exception as e:          # noqa: BLE001 - reported, not raised
            last = e
    raise last


def canary():
    """A parser that cannot fail is worse than no parser."""
    doc = json.loads('{"data":{"last_day":1,"last_week":2,"last_month":3},'
                     '"package":"x","type":"recent_downloads"}')
    assert doc["data"]["last_month"] == 3
    return True


def main():
    canary()
    audit = "--audit" in sys.argv
    rows, failed = [], []

    print("%-16s %-22s %14s %14s" % ("PACKAGE", "WHAT IT IS", "LAST WEEK",
                                     "LAST MONTH"))
    for pkg, name, what, stage in PACKAGES:
        try:
            d = json.loads(get(API % pkg))["data"]
        except Exception as e:          # noqa: BLE001
            print("%-16s  FAILED %s" % (pkg, str(e)[:46]))
            failed.append(pkg)
            continue
        rows.append({"package": pkg, "name": name, "what": what,
                     "stage": stage, "last_week": d.get("last_week"),
                     "last_month": d.get("last_month"),
                     "url": "https://pypi.org/project/%s/" % pkg})
        print("%-16s %-22s %14s %14s"
              % (pkg, what[:22], "{:,}".format(d.get("last_week") or 0),
                 "{:,}".format(d.get("last_month") or 0)))

    if failed:
        print("\nFAILED: %s" % ", ".join(failed))
    if audit:
        return 1 if failed else 0

    # Assert the run happened rather than that the data looks plausible.
    if not rows:
        print("\nREFUSING TO WRITE: every package failed.")
        return 1
    if len(failed) > len(PACKAGES) // 2:
        print("\nREFUSING TO WRITE: %d of %d packages failed."
              % (len(failed), len(PACKAGES)))
        return 1

    rows.sort(key=lambda r: -(r["last_month"] or 0))
    payload = {
        "generated": datetime.datetime.now(datetime.timezone.utc)
                     .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_name": "pypistats.org",
        "window": "last 30 days",
        "caveat": ("Client-library installs, inflated by CI. Developer reach, "
                   "not adoption, and not revenue."),
        "packages": rows,
        "failed": failed,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("\nwrote %s -- %d package(s)"
          % (os.path.relpath(OUT, ROOT), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
