#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""When each database version stops being supported, into data/lifecycle.json.

    python scripts/fetch_db_lifecycle.py
    python scripts/fetch_db_lifecycle.py --audit    # probe only, write nothing

The one fact a database administrator is actually judged on, and it is
scattered across ten vendor sites in ten formats.

WHERE THIS COMES FROM, AND WHY THAT NEEDS SAYING
------------------------------------------------
endoflife.date is a community-maintained aggregator, NOT the vendor. It is
machine-readable, which the vendors' own lifecycle pages mostly are not, and
that is the only reason it is used here. Every row therefore carries the
vendor's own page in `link`, and the page must present that as the authority
and this as the index. A date here that matters to a decision should be
checked against the vendor.

Measured 2026-11-24: all ten products resolve, 5 to 36 release cycles each.

WHAT "EOL" MEANS IS NOT THE SAME EVERYWHERE
-------------------------------------------
The API returns `eol` and `support` as either a date, `true` or `false`, and
they mean different things per product: `support` is usually active/full
support ending and `eol` is security support ending, but MySQL reports
`eol: false` with `support: true` for a current release. Booleans are kept as
booleans rather than coerced into dates -- a `false` is "not yet announced",
which is not a date and must not be rendered as one.
"""
import datetime
import io
import json
import os
import ssl
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "lifecycle.json")
UA = ("jayanthkatta.com data-platform research; contact "
      "katta.jayant@gmail.com")
API = "https://endoflife.date/api/%s.json"

# slug, display name, why it is on this page
PRODUCTS = [
    ("oracle-database", "Oracle Database", "the one I was paged for"),
    ("postgresql", "PostgreSQL", "the default new build"),
    ("mysql", "MySQL", "still everywhere"),
    ("mssqlserver", "SQL Server", "the enterprise estate"),
    ("mariadb", "MariaDB", "the fork that kept going"),
    ("mongodb", "MongoDB", "the document store that won"),
    ("redis", "Redis", "the cache everything leans on"),
    ("cassandra", "Apache Cassandra", "wide-column at scale"),
    ("elasticsearch", "Elasticsearch", "search, and accidentally analytics"),
    ("kafka", "Apache Kafka", "the log under the streams"),
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


def resolve_link(link, cycle, latest):
    """endoflife.date returns link TEMPLATES, not finished URLs.

    Elasticsearch's is
    .../release-notes/elasticsearch#elasticsearch-__LATEST__-release-notes
    and the consumer is expected to substitute. Passing it through put a raw
    __LATEST__ into an href on the page, which check_reader_facing refused --
    correctly: a reader clicking it lands nowhere.

    Substitute what we have; if a token survives, return None rather than a
    broken link. A missing link is honest, a dead one is not.
    """
    if not link:
        return None
    out = link
    for token, value in (("__LATEST__", latest), ("__RELEASE_CYCLE__", cycle)):
        if value:
            out = out.replace(token, str(value))
    return None if "__" in out else out


def as_date_or_flag(v):
    """A date stays a date; true/false stay booleans and mean 'not a date'."""
    if isinstance(v, bool) or v is None:
        return v
    s = str(v)
    try:
        datetime.date.fromisoformat(s[:10])
        return s[:10]
    except ValueError:
        return v


def days_until(v, today):
    if not isinstance(v, str):
        return None
    try:
        return (datetime.date.fromisoformat(v) - today).days
    except ValueError:
        return None


def fetch_product(slug, name, why, today):
    cycles = json.loads(get(API % slug))
    rows = []
    for c in cycles:
        eol = as_date_or_flag(c.get("eol"))
        sup = as_date_or_flag(c.get("support"))
        rows.append({
            "cycle": str(c.get("cycle")),
            "latest": c.get("latest"),
            "released": as_date_or_flag(c.get("releaseDate")),
            "latest_released": as_date_or_flag(c.get("latestReleaseDate")),
            "support_ends": sup,
            "eol": eol,
            "days_to_eol": days_until(eol, today),
            "lts": bool(c.get("lts")),
            "link": resolve_link(c.get("link"), c.get("cycle"),
                                 c.get("latest")),
        })
    dated = [r for r in rows if isinstance(r["eol"], str)]
    return {
        "slug": slug, "name": name, "why": why,
        "cycles": len(rows),
        "source": API % slug,
        "vendor_link": next((r["link"] for r in rows if r.get("link")), None),
        "newest": rows[0] if rows else None,
        # The next version to fall off support, which is the only row anybody
        # actually needs on a Monday morning.
        "next_eol": min((r for r in dated if (r["days_to_eol"] or -1) >= 0),
                        key=lambda r: r["days_to_eol"], default=None),
        "already_eol": sum(1 for r in dated if (r["days_to_eol"] or 0) < 0),
        "rows": rows,
    }


def canary():
    """A parser that cannot fail is worse than no parser."""
    assert as_date_or_flag("2031-11-19T00:00:00Z") == "2031-11-19"
    assert as_date_or_flag(False) is False, "false must stay false"
    assert as_date_or_flag(True) is True, "true must stay true"
    assert as_date_or_flag(None) is None
    today = datetime.date(2026, 11, 24)
    assert days_until("2026-12-01", today) == 7
    assert days_until(False, today) is None, "a boolean is not a date"
    return True


def main():
    canary()
    audit = "--audit" in sys.argv
    today = datetime.date.today()
    out, failed = [], []

    print("%-18s %6s %-10s %-12s %-12s %s"
          % ("PRODUCT", "CYCLES", "LATEST", "NEXT EOL", "IN DAYS", "PAST EOL"))
    for slug, name, why in PRODUCTS:
        try:
            p = fetch_product(slug, name, why, today)
        except Exception as e:          # noqa: BLE001
            print("%-18s  FAILED %s" % (name, str(e)[:50]))
            failed.append(name)
            continue
        nx = p["next_eol"]
        print("%-18s %6d %-10s %-12s %-12s %d"
              % (name, p["cycles"], str(p["newest"]["latest"])[:10],
                 str(nx["eol"]) if nx else "-",
                 str(nx["days_to_eol"]) if nx else "-", p["already_eol"]))
        out.append(p)

    if failed:
        print("\nFAILED: %s" % ", ".join(failed))
    if audit:
        return 1 if failed else 0

    # Assert the run happened rather than that the data looks plausible.
    if not out:
        print("\nREFUSING TO WRITE: every product failed.")
        return 1
    if len(failed) > len(PRODUCTS) // 2:
        print("\nREFUSING TO WRITE: %d of %d products failed."
              % (len(failed), len(PRODUCTS)))
        return 1

    payload = {
        "generated": datetime.datetime.now(datetime.timezone.utc)
                     .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_name": "endoflife.date",
        "source_note": ("Community-maintained aggregator, not the vendor. "
                        "Each product links to the vendor's own lifecycle "
                        "page, which is the authority."),
        "products": out,
        "failed": failed,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("\nwrote %s -- %d product(s), %d cycle(s)"
          % (os.path.relpath(OUT, ROOT), len(out),
             sum(p["cycles"] for p in out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
