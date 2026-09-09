#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Where the three clouds actually are, fetched rather than hardcoded.

    python scripts/fetch_regions.py
    python scripts/fetch_regions.py --dry-run

The map drew only regions that had suffered an incident, which showed where
things broke and not where anything runs. A cloud's footprint is the context
that makes the second interesting: us-east-1 appearing constantly means
something different once you can see it is one of forty-odd AWS regions.

Where each list comes from
--------------------------
    AWS    ip-ranges.json           the region field, which is the list AWS
                                    itself routes traffic for
    GCP    gstatic ipranges scopes  same idea
    Azure  its status page filter   Azure's own region dropdown, parsed out
                                    of the status page, because the download
                                    portal 403s a script

All three update themselves: a region added tomorrow appears in these feeds
without anything here changing.

Coordinates are the hard part
-----------------------------
None of the three publishes them. Checked: AWS's regional-services table has
services and no places, Azure's naming dataset has short codes and no places.
So:

    GCP    Google's own region-picker dataset carries latitude and longitude
    AWS    its dataset gives a city name -- "N. Virginia" -- matched to a
           coordinate here
    Azure  same, via the region's own name

Which means a new region in a city already known places itself, and a new
region in a NEW city arrives without a position. Those are reported, not
dropped: the page lists them as detected-but-unplaced, so the gap is visible
rather than silent. Guessing a position from the region code would put a dot
in the wrong country and look identical to a right one.
"""
import argparse
import datetime
import io
import json
import os
import re
import ssl
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import region_map  # noqa: E402

OUT = os.path.join(ROOT, "intelligence", "status", "regions.json")

AWS_LIST = "https://ip-ranges.amazonaws.com/ip-ranges.json"
AWS_NAMES = "https://raw.githubusercontent.com/jsonmaur/aws-regions/master/regions.json"
GCP_LIST = "https://www.gstatic.com/ipranges/cloud.json"
GCP_GEO = ("https://raw.githubusercontent.com/GoogleCloudPlatform/"
           "region-picker/main/data/regions.json")
AZURE_PAGE = "https://azure.status.microsoft/en-us/status/history/"

UA = "jayanthkatta.com region fetcher (+https://jayanthkatta.com)"
CTX = ssl.create_default_context()


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def city_coord(text):
    """Match a vendor's own place name to a coordinate."""
    if not text:
        return None
    t = re.sub(r"[^a-z ]", " ", text.lower())
    t = re.sub(r"\s+", " ", t).strip()
    # Longest key first, so "n virginia" beats a stray "virginia".
    for key, xy in sorted(region_map.CITY.items(), key=lambda kv: -len(kv[0])):
        probe = key.replace("-", " ")
        if probe in t:
            return xy
    return None


def fetch_aws():
    codes = sorted({p.get("region") for p in json.loads(get(AWS_LIST))["prefixes"]
                    if p.get("region") and p["region"] != "GLOBAL"})
    names = {}
    try:
        for r in json.loads(get(AWS_NAMES)):
            names[r["code"]] = r.get("full_name") or r.get("name") or ""
    except Exception:                                           # noqa: BLE001
        pass
    out = []
    for c in codes:
        xy = region_map.place(c) or city_coord(names.get(c, ""))
        out.append({"cloud": "aws", "code": c, "name": names.get(c, c),
                    "p": list(xy) if xy else None})
    return out


def fetch_gcp():
    codes = sorted({p.get("scope") for p in json.loads(get(GCP_LIST))["prefixes"]
                    if p.get("scope") and p["scope"] != "global"})
    geo = {}
    try:
        for code, meta in json.loads(get(GCP_GEO)).items():
            if meta.get("latitude") is not None:
                # Google's dataset stores magnitudes; the region's own name
                # carries the hemisphere ("Johannesburg, South Africa" is
                # south, "Sao Paulo, Brazil" is south).
                geo[code] = (meta["latitude"], meta["longitude"], meta.get("name", ""))
    except Exception:                                           # noqa: BLE001
        pass
    out = []
    for c in codes:
        xy = region_map.place(c)
        name = geo.get(c, ("", "", ""))[2] if c in geo else c
        if not xy and c in geo:
            xy = city_coord(geo[c][2])
        out.append({"cloud": "gcp", "code": c, "name": name or c,
                    "p": list(xy) if xy else None})
    return out


def fetch_azure():
    """Azure's own region filter, off its status page.

    This used to drive a headless browser, on the assumption the dropdown was
    rendered client-side. It is not -- the <select> is in the HTML as served,
    and the browser was reading the same bytes urllib gets. That mattered more
    than it sounds: nothing in CI installs a browser, so the browser version
    would have failed on every scheduled run and quietly kept serving whatever
    list happened to be committed, while reporting itself refreshed.
    """
    html = get(AZURE_PAGE)
    sel = re.search(r'<select[^>]*id="wa-dropdown-history-region".*?</select>',
                    html, re.S)
    if not sel:
        raise RuntimeError("Azure's region dropdown is no longer in the page")
    opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>',
                      sel.group(0), re.S)
    out = []
    for value, label in opts:
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", label)).strip()
        # "Non-regional" is Azure's bucket for services with no region at all.
        # Those are not places and do not belong on a map, so they are
        # excluded rather than reported as regions that cannot be drawn.
        if value in ("all", "global") or "non-regional" in value:
            continue
        xy = region_map.place(label) or city_coord(label)
        out.append({"cloud": "azure", "code": value, "name": label,
                    "p": list(xy) if xy else None})
    return out


def previous():
    """What is on disk now, per cloud."""
    try:
        with io.open(OUT, encoding="utf-8") as fh:
            old = json.load(fh)
    except Exception:                                           # noqa: BLE001
        return {}
    by = {}
    for r in old.get("regions") or []:
        by.setdefault(r.get("cloud"), []).append(r)
    return by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # Stale beats wrong.
    #
    # Azure's list is read out of its rendered status page, which means a
    # browser, which means the one part of this that can fail for reasons
    # having nothing to do with Azure. If it does, writing the result anyway
    # would silently drop seventy-odd regions off the map -- and a map missing
    # a third of Azure looks exactly like a map that is complete. So a cloud
    # that comes back empty, or noticeably smaller than what is already on
    # disk, keeps its previous entries and says so.
    was = previous()
    regions, kept = [], []
    for name, fn in (("aws", fetch_aws), ("gcp", fetch_gcp), ("azure", fetch_azure)):
        try:
            got = fn()
        except Exception as exc:                                # noqa: BLE001
            print("  %-6s FAILED %s" % (name, str(exc)[:60]))
            got = []
        before = was.get(name) or []
        if len(got) < len(before) * 0.9:
            print("  %-6s got %d against %d on disk -- keeping the old list"
                  % (name, len(got), len(before)))
            regions += before
            kept.append(name)
            continue
        placed = sum(1 for r in got if r["p"])
        print("  %-6s %3d regions, %3d placed, %3d without a known location"
              % (name, len(got), placed, len(got) - placed))
        regions += got

    if not regions:
        print("  nothing to write and nothing on disk; leaving the file alone")
        return 1

    payload = {
        "updated": datetime.datetime.now(datetime.timezone.utc)
                   .isoformat(timespec="seconds").replace("+00:00", "Z"),
        "sources": {"aws": AWS_LIST, "gcp": GCP_LIST, "azure": AZURE_PAGE},
        # Which clouds this run could not re-read. The page shows it, because
        # "refreshed today" over a list that is actually a week old is the
        # kind of quiet lie this whole section exists to avoid.
        "stale": kept,
        "regions": regions,
    }
    if args.dry_run:
        print("  dry run: nothing written")
        return 0
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    os.replace(tmp, OUT)
    print("  %d regions -> %s" % (len(regions), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
