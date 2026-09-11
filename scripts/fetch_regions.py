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
import math
import os
import re
import ssl
import sys
import unicodedata
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import region_map  # noqa: E402

OUT = os.path.join(ROOT, "intelligence", "status", "regions.json")

AWS_LIST = "https://ip-ranges.amazonaws.com/ip-ranges.json"
# AWS names its own regions in its General Reference, one table of Name and
# Code. This replaced a community-maintained JSON that was missing every
# region added since it was last updated -- sixteen of forty-two had no
# name at all, which on the map meant sixteen dots that could not say
# where they were. A vendor page that lags is a vendor problem; a third
# party that lags is a problem I chose.
AWS_NAMES = "https://docs.aws.amazon.com/general/latest/gr/rande.html"
# AWS's own global-infrastructure page. Its embedded JSON is the only
# public, machine-readable statement of AWS zone counts. See
# aws_zone_counts() for why every row from it is validated first.
AWS_GLOBAL = ("https://aws.amazon.com/about-aws/global-infrastructure/regions_az/")
GCP_LIST = "https://www.gstatic.com/ipranges/cloud.json"
GCP_GEO = ("https://raw.githubusercontent.com/GoogleCloudPlatform/"
           "region-picker/main/data/regions.json")
AZURE_PAGE = "https://azure.status.microsoft/en-us/status/history/"

# Where each vendor states the physical detail a reader actually wants: which
# city, which country, and how many zones. None of it is in the machine feeds.
AZURE_DOCS = "https://learn.microsoft.com/en-us/azure/reliability/regions-list"
GCP_ZONES = "https://cloud.google.com/compute/docs/regions-zones"

UA = "jayanthkatta.com region fetcher (+https://jayanthkatta.com)"
CTX = ssl.create_default_context()


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def city_coord(text):
    """Match a vendor's own place name to a coordinate.

    Accents are folded first: Google writes "Sao Paulo" and AWS writes
    "Sao Paulo" with the tilde, Azure writes "Montreal" with the acute and
    "Queretaro State" with one too. Those are the same three places, and
    comparing them byte for byte quietly loses the dot.
    """
    if not text:
        return None
    text = "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c))
    t = re.sub(r"[^a-z ]", " ", text.lower())
    t = re.sub(r"\s+", " ", t).strip()
    # Longest key first, so "n virginia" beats a stray "virginia".
    for key, xy in sorted(region_map.CITY.items(), key=lambda kv: -len(kv[0])):
        probe = key.replace("-", " ")
        if probe in t:
            return xy
    return None


def azure_detail():
    """Azure's own region table: physical city, country, and zone support.

    Azure documents more about its regions than the other two put together --
    the city each one is in, the geography it belongs to, and whether it has
    availability zones. It is an HTML table rather than a feed, so this is a
    parse of a documentation page and is treated as one: if the table moves,
    the detail disappears and the regions still draw.
    """
    out = {}
    try:
        html = get(AZURE_DOCS)
    except Exception:                                           # noqa: BLE001
        return out
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        if len(cells) < 6:
            continue
        def flat(x):
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip()
        name = flat(cells[0])
        code = flat(cells[5])
        if not code or code == "Programmatic name":
            continue
        out[name] = {
            # The zone column is a checkmark image; its alt text is the value.
            "az": bool(re.search(r'alt="Yes"', cells[1], re.I)),
            "city": flat(cells[3]),
            "country": flat(cells[4]),
            "arm": code,
        }
    return out


def gcp_zones():
    """Google's zone list, which is the one real zone count of the three."""
    out = {}
    try:
        html = get(GCP_ZONES)
    except Exception:                                           # noqa: BLE001
        return out
    for z in set(re.findall(
            r"\b((?:us|eu|europe|asia|australia|northamerica|southamerica|me|"
            r"africa)-[a-z]+\d+)-([a-z])\b", html)):
        out.setdefault(z[0], set()).add(z[0] + "-" + z[1])
    return {k: sorted(v) for k, v in out.items()}


# The three do not spell countries the same way. Google writes "USA", Azure
# writes "United States"; shown side by side in one heading they looked like
# two countries.
SAME_COUNTRY = {
    "USA": "United States", "US": "United States",
    "UK": "United Kingdom", "UAE": "United Arab Emirates",
    "Korea": "South Korea",
}


# Azure's "Geography" column is its own grouping, not a country: North Europe
# comes back as "Europe" and East Asia as "Asia Pacific". Storing those as the
# country made the map claim a region was in a continent, and made the
# placement check unable to verify any of them.
NOT_A_COUNTRY = {"europe", "asia pacific", "americas", "middle east", "africa",
                 "global", "azure government", "china"}


def one_country(name):
    name = (name or "").strip()
    if name.lower() in NOT_A_COUNTRY:
        return ""
    return SAME_COUNTRY.get(name, name)


def split_place(text):
    """"Johannesburg, South Africa" -> ("Johannesburg", "South Africa")."""
    if not text:
        return "", ""
    parts = [x.strip() for x in text.split(",")]
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return parts[0], ""


def in_parens(text):
    """"Asia Pacific (Mumbai)" -> "Mumbai". AWS names its city, not its country."""
    m = re.search(r"\(([^)]+)\)", text or "")
    return m.group(1).strip() if m else ""


def haversine(a, b):
    """Kilometres between two (lat, lng) pairs."""
    la1, lo1, la2, lo2 = [math.radians(x) for x in (a[0], a[1], b[0], b[1])]
    d = (math.sin((la2 - la1) / 2) ** 2 +
         math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(d))


def aws_zone_counts(placed):
    """How many availability zones each AWS region has, where it can be trusted.

    AWS's own global-infrastructure page carries a JSON blob of every region:
    an id, a name, a latitude and longitude, and a zone count. It is the only
    public, machine-readable statement of those counts -- and it is a marketing
    page, which shows.

    Its ids arrive with trailing spaces ("eu-west-2 "), it lists codes that do
    not exist ("cn-north-4", "ap-southeast-7x"), and it puts ap-southeast-7 --
    Thailand -- in New Zealand, 9,573 km away. Printing a number off a row like
    that is how a wrong figure gets a confident label.

    So each row is validated against a location this site already holds,
    arrived at independently: if AWS's coordinate for a code sits more than
    500 km from ours, the row is about a different place and its count is
    dropped. The furthest row that passes is 234 km -- Boardman against
    Portland, for Oregon -- so the gate has room without being wide enough to
    admit a continent error.

    `placed` maps region code to the [lat, lng] this site already carries. A
    region we cannot place cannot be validated, so it gets no count. That is
    the honest outcome rather than the convenient one.
    """
    out = {}
    try:
        html = get(AWS_GLOBAL)
    except Exception:                                           # noqa: BLE001
        return out
    i = html.find('"continents":"')
    if i < 0:
        return out
    raw = html[i + len('"continents":"'): i + 400000]
    raw = raw.replace('\\"', '"').replace("\\\\", "\\")
    try:
        # The attribute runs on past the array, so decode the array and stop.
        blob, _end = json.JSONDecoder().raw_decode(raw)
    except Exception:                                           # noqa: BLE001
        return out
    for cont in blob:
        for r in cont.get("regions") or []:
            code = (r.get("id") or "").strip()
            n = r.get("availabilityZones")
            if not code or not isinstance(n, int) or not 1 <= n <= 12:
                continue
            mine = placed.get(code)
            if not mine or r.get("lat") is None or r.get("lng") is None:
                continue
            if haversine(mine, (r["lat"], r["lng"])) > 500:
                continue
            out[code] = n
    return out


def fetch_aws():
    codes = sorted({p.get("region") for p in json.loads(get(AWS_LIST))["prefixes"]
                    if p.get("region") and p["region"] != "GLOBAL"})
    names = {}
    try:
        html = get(AWS_NAMES)
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
            # Name first, Code second.
            if len(cells) >= 2 and re.match(
                    r"^[a-z]{2,4}(?:-[a-z]+)+-\d$", cells[1]):
                names[cells[1]] = cells[0]
    except Exception:                                           # noqa: BLE001
        pass
    out = []
    placed = {}
    for c in codes:
        label = names.get(c, "")
        city = in_parens(label) or label
        xy = city_coord(city) or region_map.place(c)
        if xy:
            placed[c] = list(xy)
        out.append({
            "cloud": "aws", "code": c, "name": label or c,
            "city": city,
            # AWS states the city in the region's own name and the country
            # nowhere machine-readable, so the country comes from the city.
            "country": one_country(region_map.country_of(c, city)),
            # AWS names no zones, so there is no list to hold. The count comes
            # below, from AWS's own page, and only where it can be checked.
            "zones": [], "az": None,
            "p": list(xy) if xy else None,
        })

    counts = aws_zone_counts(placed)
    for r in out:
        n = counts.get(r["code"])
        if n:
            r["az_n"] = n
            r["az"] = True
    print("  aws zone counts: %d of %d regions, validated against a location "
          "already held" % (len(counts), len(out)))
    return out


def fetch_gcp():
    codes = sorted({p.get("scope") for p in json.loads(get(GCP_LIST))["prefixes"]
                    if p.get("scope") and p["scope"] != "global"})
    geo = {}
    try:
        for code, meta in json.loads(get(GCP_GEO)).items():
            geo[code] = meta.get("name", "")
    except Exception:                                           # noqa: BLE001
        pass
    zones = gcp_zones()
    out = []
    for c in codes:
        label = geo.get(c, "")
        city, country = split_place(label)
        xy = (city_coord(city) if city else None) or region_map.place(c)
        out.append({
            "cloud": "gcp", "code": c, "name": label or c,
            "city": city,
            "country": one_country(country or region_map.country_of(c, city)),
            # Google lists its zones by name, so this is a count of named
            # things rather than an assertion about capacity.
            "zones": zones.get(c, []),
            "az": bool(zones.get(c)),
            "p": list(xy) if xy else None,
        })
    return out


def fetch_azure():
    """Azure's regions, from its status filter AND its reliability docs.

    The status page's <select> is in the HTML as served, so this needs no
    browser -- which matters, because nothing in CI installs one and the
    browser version would have failed on every scheduled run while reporting
    itself refreshed.

    It is also not a stable list. Fetched repeatedly within a minute the same
    URL returned 74 options and then 76: Azure serves variants, and which one
    you get is luck. India South Central (Hyderabad) was in this file because
    one fetch happened to include it, and absent from the next fetch entirely.
    A map that gains and loses a region depending on which copy of a page it
    caught is not a map anyone should trust.

    So the list is the union of two things Azure publishes:

        the status filter    every region it will report incidents for,
                             including the Jio, China and Government regions
                             the docs do not cover
        the reliability docs  a stable table carrying the physical city, the
                             geography and whether the region has availability
                             zones

    Neither alone is complete and neither is a guess. Where they disagree
    about existence, the region is included -- a region named by either arm of
    Microsoft is a region -- and where only one carries detail, that detail is
    used.
    """
    detail = azure_detail()

    out, seen = [], set()

    def add(code, label, d):
        key = (label or code).lower()
        if key in seen:
            return
        seen.add(key)
        xy = city_coord((d or {}).get("city") or "") or region_map.place(label)
        out.append({
            "cloud": "azure", "code": code, "name": label,
            "city": (d or {}).get("city", ""),
            # Azure publishes whether a region has zones, not how many, so
            # this is a flag and never a count.
            "country": (one_country((d or {}).get("country", "")) or
                        region_map.country_of(label, (d or {}).get("city", ""))),
            "zones": [], "az": (d or {}).get("az"),
            "p": list(xy) if xy else None,
        })

    html = get(AZURE_PAGE)
    sel = re.search(r'<select[^>]*id="wa-dropdown-history-region".*?</select>',
                    html, re.S)
    if not sel:
        raise RuntimeError("Azure's region dropdown is no longer in the page")
    for value, label in re.findall(
            r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', sel.group(0), re.S):
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", label)).strip()
        # "Non-regional" is Azure's bucket for services with no region at all.
        # Those are not places and do not belong on a map.
        if value in ("all", "global") or "non-regional" in value:
            continue
        add(value, label, detail.get(label))

    # Anything the docs know about that the filter did not serve this time.
    for label, d in sorted(detail.items()):
        add(d.get("arm") or label, label, d)

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
        missing = sorted({r.get("city") for r in got
                          if not r["p"] and r.get("city")})
        if missing:
            print("         cities named but not in the coordinate table: %s"
                  % ", ".join(missing))
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
