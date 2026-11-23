#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quarterly revenue for the independent data platforms, from SEC XBRL.

    python scripts/fetch_data_economics.py

Writes data/economics.json. Reuses fetch_cloud_economics.get() so there is
one place that knows the SEC's rate limit and its User-Agent rule.

WHY THESE FIRMS
---------------
The page argues that the data platform moved from a box in a rack to a line
item in a cloud bill. These are the firms that argument can be checked
against: the cloud-native platforms, and the incumbent they displaced.
Teradata is in the list precisely because it is shrinking -- a page that
printed only the winners would be making the case by selection.

Two have no filing to read and are listed anyway, with the reason, because a
missing vendor reads as a vendor doing nothing.

WHAT THE NUMBER IS
------------------
Total company revenue for the most recent quarter, from the company's own
10-Q or 10-K. NOT a data-platform segment: none of these break one out, and
inventing a split would be the error that makes a page like this worthless.
For Snowflake and MongoDB total revenue IS the data platform; for Elastic it
is search plus observability plus security, and the page says so.

THE CONCEPT NAME IS NOT THE SAME EVERYWHERE
-------------------------------------------
us-gaap:Revenues returns 404 for Snowflake. Every firm here reports under
RevenueFromContractWithCustomerExcludingAssessedTax instead, but that is a
fact measured on 2026-11-22, not a rule -- CONCEPTS is tried in order and the
run fails loudly rather than reporting a firm as having no revenue.
"""
import datetime
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
OUT = os.path.join(ROOT, "data", "economics.json")

CONCEPTS = ["RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "RevenueFromContractWithCustomerIncludingAssessedTax"]

# name, ticker, CIK, what the revenue actually covers
FIRMS = [
    ("Snowflake", "SNOW", "0001640147", "the data cloud; all of it"),
    ("MongoDB", "MDB", "0001441816", "Atlas plus the self-managed server"),
    ("Elastic", "ESTC", "0001707753", "search, observability and security"),
    ("Teradata", "TDC", "0000816761", "the incumbent warehouse"),
]
# No filing to read, for two different reasons, and the page states which.
# Confluent is here because the staleness check caught it: its newest
# quarterly fact was 418 days old, which looked like a broken fetcher and was
# not -- it filed Form 15-12G on 2026-03-27 and deregistered. A page that had
# simply printed the newest number it could find would have shown a year-old
# quarter under a heading promising the latest, indefinitely.
PRIVATE = [
    ("Databricks", "private; has never filed", None, None),
    ("Confluent", "deregistered 2026-03-27 (Form 15-12G); last reported "
                  "quarter stands", "2025-09-30", 298_900_000),
]


def quarters(rows):
    """Rows that cover one quarter. A 10-K carries the full year too."""
    out = []
    for x in rows:
        if x.get("form") not in ("10-Q", "10-K") or not x.get("start"):
            continue
        try:
            days = (datetime.date.fromisoformat(x["end"])
                    - datetime.date.fromisoformat(x["start"])).days
        except ValueError:
            continue
        if 80 <= days <= 100:
            out.append(x)
    out.sort(key=lambda x: x["end"])
    return out


def firm(get, name, tick, cik, covers):
    for concept in CONCEPTS:
        url = ("https://data.sec.gov/api/xbrl/companyconcept/CIK%s/us-gaap/"
               "%s.json" % (cik, concept))
        try:
            doc = json.loads(get(url, tries=2))
        except Exception:               # noqa: BLE001 - try the next concept
            continue
        q = quarters(doc.get("units", {}).get("USD", []))
        if not q:
            continue
        last = q[-1]
        # Year on year against the quarter ending in the same month, which is
        # the only honest comparison for firms whose fiscal year is not the
        # calendar one -- Snowflake's Q2 ends 31 July.
        prior = [x for x in q
                 if x["end"][5:7] == last["end"][5:7]
                 and int(x["end"][:4]) == int(last["end"][:4]) - 1]
        yoy = ((last["val"] / prior[-1]["val"] - 1) * 100) if prior else None
        return {"name": name, "ticker": tick, "cik": cik, "covers": covers,
                "concept": concept, "quarter_end": last["end"],
                "revenue_usd": last["val"], "yoy_pct": yoy,
                "form": last.get("form"), "accn": last.get("accn", "")}
    return {"name": name, "ticker": tick, "cik": cik, "covers": covers,
            "error": "no quarterly revenue found under %d concepts"
                     % len(CONCEPTS)}


def main():
    import fetch_cloud_economics as fce

    rows = [firm(fce.get, *f) for f in FIRMS]
    failed = [r["name"] for r in rows if "error" in r]

    print("%-10s %-6s %-12s %12s  %9s  %s"
          % ("FIRM", "TICKER", "QUARTER END", "REVENUE", "YoY", "FORM"))
    for r in rows:
        if "error" in r:
            print("%-10s %-6s  %s" % (r["name"], r["ticker"], r["error"]))
            continue
        print("%-10s %-6s %-12s %11.3fB  %8s  %s"
              % (r["name"], r["ticker"], r["quarter_end"],
                 r["revenue_usd"] / 1e9,
                 ("%+.0f%%" % r["yoy_pct"]) if r["yoy_pct"] is not None
                 else "-", r.get("form")))
    for name, why, qe, val in PRIVATE:
        extra = ("  last %s $%.3fB" % (qe, val / 1e9)) if qe else ""
        print("%-10s %-6s  %s%s" % (name, "-", why, extra))

    if failed:
        print("\nREFUSING TO WRITE: no revenue for %s" % ", ".join(failed))
        return 1

    # The staleness that matters is a quarter nobody noticed had not arrived.
    today = datetime.date.today()
    for r in rows:
        age = (today - datetime.date.fromisoformat(r["quarter_end"])).days
        r["quarter_age_days"] = age
        if age > 190:
            print("\nWARNING: %s's newest filing is %d days old -- either the "
                  "concept moved or the filing was missed." % (r["name"], age))

    payload = {"generated": datetime.datetime.now(datetime.timezone.utc)
                            .strftime("%Y-%m-%dT%H:%M:%SZ"),
               "firms": rows,
               "private": [{"name": n, "why": w, "last_quarter_end": qe,
                             "last_revenue_usd": v}
                           for n, w, qe, v in PRIVATE]}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("\nwrote %s -- %d firms" % (os.path.relpath(OUT, ROOT), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
