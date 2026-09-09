#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google Cloud's older incidents, from its per-product history pages.

    python scripts/fetch_gcp_history.py            # refresh
    python scripts/fetch_gcp_history.py --limit 5  # only N products
    python scripts/fetch_gcp_history.py --dry-run

Why this exists
---------------
incidents.json is a rolling window. It carried six incidents, none older than
27 February 2026, and ignores ?since, ?limit and ?all -- so the status page
could show Google back to February while AWS reached 2011 and Azure 2021.
Read as a comparison between vendors that says Google discloses least, and it
says nothing of the sort: Google had outages in 2022, and this site simply
could not see them.

Google does publish them, one page per product:

    status.cloud.google.com/products.json          212 products, each an id
    status.cloud.google.com/products/<id>/history  that product's incidents

Each history page carries a table of Summary, Date and Duration with a link to
the incident, so the incident text is on the page already -- no second fetch
per incident, which matters when there are 212 of them.

What this does NOT do
---------------------
It does not invent a start time. The history table gives a date and a duration
in Google's own words; where a duration cannot be read, the incident is stored
with the date alone rather than a fabricated window. A day is a fact; an
invented hour is not.
"""
import argparse
import concurrent.futures
import datetime
import io
import json
import os
import re
import ssl
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "intelligence", "gcp-history.json")

PRODUCTS = "https://status.cloud.google.com/products.json"
HISTORY = "https://status.cloud.google.com/products/%s/history"
INCIDENT = "https://status.cloud.google.com/incidents/%s"

UA = "jayanthkatta.com history fetcher (+https://jayanthkatta.com)"
CTX = ssl.create_default_context()


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def flat(s, limit=400):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()[:limit]


# "Feb 22, 2022" and "22 Feb 2022" both appear across products.
DATE_A = re.compile(r"([A-Z][a-z]{2})\s+(\d{1,2}),\s*(20\d\d)")
DATE_B = re.compile(r"(\d{1,2})\s+([A-Z][a-z]{2})\s+(20\d\d)")
MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def parse_date(text):
    m = DATE_A.search(text)
    if m and m.group(1) in MON:
        return "%s-%02d-%02d" % (m.group(3), MON.index(m.group(1)) + 1, int(m.group(2)))
    m = DATE_B.search(text)
    if m and m.group(2) in MON:
        return "%s-%02d-%02d" % (m.group(3), MON.index(m.group(2)) + 1, int(m.group(1)))
    return ""


def parse_history(html, product):
    """Rows of Summary / Date / Duration, each linking to an incident."""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        link = re.search(r"incidents/([A-Za-z0-9]{8,})", row)
        if not link:
            continue                      # header row
        cells = [flat(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        cells = [c for c in cells if c]
        if not cells:
            continue
        summary = cells[0]
        rest = " ".join(cells[1:])
        date = parse_date(rest) or parse_date(summary)
        out.append({
            "cloud": "gcp",
            "id": link.group(1),
            "title": summary,
            "service": product,
            "region": "",
            "begin": date,
            "end": date,
            "duration": cells[-1] if len(cells) > 2 else "",
            "update": "",
            "updates": 0,
            "url": INCIDENT % link.group(1),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    products = json.loads(get(PRODUCTS)).get("products") or []
    if args.limit:
        products = products[:args.limit]
    print("  %d product(s) to read" % len(products))

    found, failed = {}, 0

    def one(p):
        try:
            return p, parse_history(get(HISTORY % p["id"]), p.get("title", ""))
        except Exception:                                       # noqa: BLE001
            return p, None

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for p, rows in pool.map(one, products):
            done += 1
            if rows is None:
                failed += 1
            else:
                for r in rows:
                    # One incident can touch several products. Keep the first
                    # and record the others rather than storing it twice.
                    if r["id"] in found:
                        svc = found[r["id"]]["service"]
                        if p.get("title") and p["title"] not in svc:
                            found[r["id"]]["service"] = (svc + ", " + p["title"])[:200]
                    else:
                        found[r["id"]] = r
            if done % 50 == 0:
                print("   ...%d/%d products" % (done, len(products)), flush=True)

    dated = [r for r in found.values() if r.get("begin")]
    years = {}
    for r in dated:
        years[r["begin"][:4]] = years.get(r["begin"][:4], 0) + 1
    print("  %d unique incident(s), %d dated, %d product page(s) failed"
          % (len(found), len(dated), failed))
    print("  by year:", dict(sorted(years.items(), reverse=True)))

    if args.dry_run:
        print("  dry run: nothing written")
        return 0

    payload = {
        "updated": datetime.datetime.now(datetime.timezone.utc)
                   .isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": PRODUCTS,
        "products_read": len(products),
        "products_failed": failed,
        "incidents": sorted(found.values(), key=lambda r: r.get("begin") or "",
                            reverse=True),
    }
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, OUT)
    print("  -> %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
