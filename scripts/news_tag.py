#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Classify stored announcements by kind, and tag them with services.

Two separate jobs, and the order matters.

CLASSIFY FIRST
--------------
The store is not one kind of thing. Measured on the first ingest:

    azure   MSRC Update Guide      4,353   83% of the whole Azure store
            Azure Updates (RSS)      200   the actual announcement feed
    aws     What's New               100
            Security Bulletins        97
            18 blog feeds            320

Most of the Azure data is Microsoft vulnerability notices, many not about Azure
at all -- which is why an early "what's new with Azure resources" probe came
back full of arm64 kernel CVEs. Tagging services without first separating
announcements from CVEs from customer stories produces tags that are individually
correct and answers that are still useless.

Class comes from the SOURCE, not from the text. The fetchers already know which
feed a row came from, and a feed's whole purpose is stable in a way a headline
is not.

THEN TAG, IN TIERS
------------------
Each record records HOW it was tagged, not just the result, so a reader-facing
answer can later choose to trust only the top tiers rather than being forced to
take all of it or none:

    vendor     the cloud told us. GCP puts the product in a heading, and the
               fetcher already captures it -- 100% coverage, authoritative.
    title      the vendor's own naming convention. AWS opens 87% of What's New
               items with "Amazon X" or "AWS X"; Azure Updates prefixes a status
               ("Generally Available: Azure X"). Deterministic and reviewable.
    catalogue  a service name found loose in the text. Lowest confidence, and
               the reason ambiguous names are handled separately below.
    none       nothing matched. Recorded, never silently dropped -- an untagged
               record must stay countable or coverage numbers become a fiction.

WHY AMBIGUOUS NAMES ARE NOT JUST MATCHED
----------------------------------------
39 of the 683 AWS service names are ordinary English words: Backup, Batch,
Config, Connect, Health, Glue, Organizations, Detective, Forecast. Matching
those loose would tag every announcement containing the word "backup" as an AWS
Backup announcement. They are only accepted when the vendor's own prefix vouches
for them -- "AWS Backup", never a bare "backup".
"""
import argparse
import io
import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import news_store as store            # noqa: E402  (path set above)

CLOUDS = store.CLOUDS


# ── classification ──────────────────────────────────────────────
# Source name -> class. Anything unlisted falls through to "blog", which is the
# safe default: a blog post mis-filed as an announcement pollutes the answer a
# reader trusts most, while an announcement mis-filed as a blog post is merely
# ranked lower.
CLASS_BY_SOURCE = {
    "aws": {
        "What's New": "announcement",
        "Security Bulletins": "security",
    },
    "azure": {
        "Azure Updates (RSS)": "announcement",
        "MSRC Update Guide": "security",
        "Microsoft Security": "security",
        # GitHub release feeds: real product releases, not editorial.
        "Azure CLI releases": "release",
        "Bicep releases": "release",
        "AKS releases": "release",
        "Terraform AzureRM": "release",
    },
    "gcp": {
        "Release Notes": "announcement",
        "Security Bulletins": "security",
        "GKE Sec Bulletins": "security",
    },
}


def classify(cloud, record):
    return CLASS_BY_SOURCE.get(cloud, {}).get(record.get("source", ""), "blog")


# ── catalogues ──────────────────────────────────────────────────

def _catalogue(cloud):
    p = os.path.join(SCRIPTS, "%s_services.json" % cloud)
    if not os.path.isfile(p):
        return {}
    return json.load(io.open(p, encoding="utf-8")).get("services", {})


def _compiled(cloud):
    """(regex, name) pairs, longest name first so 'API Gateway' wins over 'API'.

    Ambiguous entries are kept separate rather than dropped: they are still
    usable when a vendor prefix vouches for them.
    """
    cat = _catalogue(cloud)
    safe, risky = [], []
    for name, meta in cat.items():
        if len(name) < 2:
            continue
        rx = re.compile(r"(?<![\w-])%s(?![\w-])" % re.escape(name), re.I)
        (risky if (isinstance(meta, dict) and meta.get("ambiguous")) else safe
         ).append((rx, name))
    key = lambda pair: -len(pair[1])
    return sorted(safe, key=key), sorted(risky, key=key)


_CACHE = {}


def catalogues(cloud):
    if cloud not in _CACHE:
        _CACHE[cloud] = _compiled(cloud)
    return _CACHE[cloud]


# ── title conventions ───────────────────────────────────────────
# AWS opens an announcement with the service, near enough always.
AWS_PREFIX = re.compile(r"^(?:Amazon|AWS)\s+(.{2,60}?)(?=\s+(?:now|is|are|has|"
                        r"adds|announces|introduces|supports|launches|expands|"
                        r"available|adds?|releases)\b|,|:|\s*$)", re.I)

# Azure Updates prefixes a lifecycle status before the service -- TWICE. The
# real shape is:
#
#     [Launched] Generally Available: Azure API Management Premium v2 ...
#     [In preview] Public Preview: Azure SQL updates for early-June
#
# Stripping only the "Generally Available:" half left the bracket in front of it
# and the anchor never matched, which is most of why Azure announcements tagged
# at 23% while AWS managed 94%. Both prefixes come off, in order.
#
# The bracket is not noise: it is the lifecycle state, and it is the one piece
# of metadata a reader asking "what is new" most wants and neither AWS nor GCP
# publishes this cleanly. It is captured as `status` rather than discarded.
AZURE_BRACKET = re.compile(r"^\[\s*([^\]]{1,40}?)\s*\]\s*")
AZURE_STATUS = re.compile(
    r"^(?:generally\s+available|general\s+availability|public\s+preview|"
    r"private\s+preview|preview|retirement|retiring|ga|update|announcing|"
    r"launched|in\s+development|deprecation)\s*:\s*", re.I)


def azure_strip(head):
    """Return (title without prefixes, lifecycle status or '')."""
    status = ""
    m = AZURE_BRACKET.match(head)
    if m:
        status = m.group(1).strip()
        head = head[m.end():]
    m = AZURE_STATUS.match(head)
    if m:
        # The inner status is more specific than the bracket when both exist
        # ("Public Preview" vs "In preview"), so it wins.
        status = head[:m.end()].strip(" :") or status
        head = head[m.end():]
    return head.strip(), status


def _match_catalogue(text, cloud, allow_risky_after=None):
    """Service names found in `text`. Ambiguous names need a vouching prefix."""
    safe, risky = catalogues(cloud)
    found = []
    for rx, name in safe:
        if rx.search(text):
            found.append(name)
    if allow_risky_after:
        for rx, name in risky:
            m = rx.search(text)
            if m and allow_risky_after.search(text[:m.start()] or ""):
                found.append(name)
    # Drop a name wholly contained in a longer match: 'API Gateway' implies
    # nothing useful is added by also reporting 'API'.
    out = []
    for n in found:
        if not any(n != o and n.lower() in o.lower() for o in found):
            out.append(n)
    return sorted(set(out))


VOUCHER = {"aws": re.compile(r"\b(?:Amazon|AWS)\s*$", re.I),
           "azure": re.compile(r"\b(?:Azure|Microsoft)\s*$", re.I),
           "gcp": re.compile(r"\b(?:Google|Cloud)\s*$", re.I)}

# Vendor-branded phrases that are not services. GovCloud and the Region names
# are *places*; tagging them as services put "AWS GovCloud" beside "Amazon
# Bedrock" as though a reader could ask what is new in it.
STOP_TAGS = {
    "aws govcloud", "aws region", "aws regions", "amazon web services",
    "aws cloud", "aws account", "aws accounts", "aws management console",
    "azure portal", "azure regions", "azure region", "microsoft azure",
    "azure government", "azure cloud",
}


def _canonical(phrase, cloud):
    """Snap a raw title fragment to catalogue names it contains.

    Without this the tag is whatever the headline happened to say -- "Amazon
    Connect Customer" and "Azure Chaos Studio Workspaces and Scenarios" both
    became their own services, so a reader filtering on Connect would miss them.
    Falls back to the phrase itself when the catalogue has nothing, which is the
    only option for Azure: 24 curated entries cannot cover 200 announcements.
    """
    hits = _match_catalogue(phrase, cloud, re.compile(r".*", re.S))
    return hits or ([phrase] if phrase.lower() not in STOP_TAGS else [])

# A vendor-branded name appearing anywhere in a title. Capitalisation is the
# signal: "Azure Files" is a product, "azure files" would be prose. Capped at
# three trailing words so a long title cannot be swallowed whole.
_CAP = r"(?:[A-Z][\w\-\.]*|AI|API|SQL|OS|VM|VMs|ML|IoT)"
INLINE = {
    "aws": re.compile(r"\b(?:Amazon|AWS)\s+%s(?:\s+%s){0,2}" % (_CAP, _CAP)),
    "azure": re.compile(r"\b(?:Azure|Microsoft)\s+%s(?:\s+%s){0,2}"
                        % (_CAP, _CAP)),
}


def tag(cloud, record):
    """Return (services, method).

    Every tier that fires contributes; they are unioned rather than raced. The
    first version returned the first tier that matched, which is why "AWS Batch
    now supports Amazon ECS Managed Instances" came back as Batch alone and
    "AWS Transform announces GA of Amazon FSx for NetApp" lost FSx entirely --
    a reader filtering on ECS would never have seen either. `method` reports the
    strongest tier that contributed, so confidence is still expressible.
    """
    head = record.get("headline", "") or ""

    # Tier 1 -- the vendor told us. GCP only, and it is authoritative.
    if cloud == "gcp":
        product = (record.get("product") or "").strip()
        if product and product.lower() not in ("security bulletin",):
            if product.lower() == "gke security bulletin":
                return ["Google Kubernetes Engine"], "vendor"
            return [product], "vendor"

    text = azure_strip(head)[0] if cloud == "azure" else head
    names, tiers = [], []

    # Tier 2 -- the vendor's own title convention, at the start of the title.
    lead = None
    if cloud == "aws":
        m = AWS_PREFIX.match(text)
        if m:
            lead = m.group(1).strip(" .,:-")
    elif cloud == "azure":
        m = re.match(r"^(Azure|Microsoft)\s+((?:[A-Z][\w\-\.]*|for|of|and|AI|"
                     r"API|SQL|OS|VM|VMs)(?:\s+(?:[A-Z][\w\-\.]*|for|of|and|"
                     r"AI|API|SQL|OS|VM|VMs)){0,4})", text)
        if m:
            lead = ("%s %s" % (m.group(1), m.group(2))).strip(" .,:-")
    if lead and 2 < len(lead) <= 60:
        got = _canonical(lead, cloud)
        if got:
            names += got
            tiers.append("title")

    # Tier 2b -- vendor-branded names anywhere else in the title.
    inline = INLINE.get(cloud)
    if inline:
        for m in inline.finditer(text):
            phrase = re.sub(r"\s+", " ", m.group(0)).strip(" .,:-")
            if 4 < len(phrase) <= 45:
                got = _canonical(phrase, cloud)
                if got:
                    names += got
                    tiers.append("inline")

    # Tier 3 -- catalogue names loose in the text. This is what recovers the
    # SECOND service in "X now supports Y", which the leading match cannot see.
    got = _match_catalogue(text, cloud, VOUCHER[cloud])
    if got:
        names += got
        tiers.append("catalogue")

    names = [n for n in names if n.lower() not in STOP_TAGS]
    # Prefer the longest form of overlapping names, then de-duplicate.
    keep = [n for n in names
            if not any(n != o and n.lower() in o.lower() for o in names)]
    keep = sorted(set(keep))
    if not keep:
        return [], "none"
    for t in ("title", "inline", "catalogue"):
        if t in tiers:
            return keep[:4], t
    return keep[:4], "catalogue"


# ── applying it to the store ────────────────────────────────────

def apply(clouds=CLOUDS, dry_run=False):
    summary = []
    for cloud in clouds:
        counts = {"vendor": 0, "title": 0, "inline": 0,
                  "catalogue": 0, "none": 0}
        classes = {}
        total = 0
        for ym in store.all_months(cloud):
            recs = store.load_month(cloud, ym)
            for r in recs.values():
                r["class"] = classify(cloud, r)
                services, method = tag(cloud, r)
                r["services"] = services
                r["tag_method"] = method
                counts[method] += 1
                classes[r["class"]] = classes.get(r["class"], 0) + 1
                total += 1
            if not dry_run:
                store.save_month(cloud, ym, recs)
        summary.append((cloud, total, counts, classes))
    return summary


def sample(cloud, n, cls=None, method=None, seed=None):
    rows = []
    for ym in store.all_months(cloud):
        rows.extend(store.load_month(cloud, ym).values())
    if cls:
        rows = [r for r in rows if r.get("class") == cls]
    if method:
        rows = [r for r in rows if r.get("tag_method") == method]
    rnd = random.Random(seed)
    rnd.shuffle(rows)
    return rows[:n]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("apply", help="classify and tag every stored record")
    p.add_argument("--cloud", choices=CLOUDS, action="append")
    p.add_argument("--dry-run", action="store_true")

    s = sub.add_parser("sample", help="print a random sample for hand-checking")
    s.add_argument("cloud", choices=CLOUDS)
    s.add_argument("-n", type=int, default=25)
    s.add_argument("--class", dest="cls")
    s.add_argument("--method")
    s.add_argument("--seed", type=int, default=None)

    args = ap.parse_args()

    if args.cmd == "sample":
        for r in sample(args.cloud, args.n, args.cls, args.method, args.seed):
            print("  [%-9s %-9s] %-70s -> %s"
                  % (r.get("class", "?"), r.get("tag_method", "?"),
                     r["headline"][:70], ", ".join(r.get("services") or []) or "-"))
        return 0

    if args.cmd != "apply":
        ap.print_help()
        return 2

    clouds = tuple(args.cloud) if args.cloud else CLOUDS
    for cloud, total, counts, classes in apply(clouds, args.dry_run):
        print("\n  %s -- %d records" % (cloud.upper(), total))
        print("    class : " + ", ".join("%s=%d" % kv
                                         for kv in sorted(classes.items())))
        tagged = total - counts["none"]
        pct = (100.0 * tagged / total) if total else 0
        print("    tagged: %d/%d (%.0f%%)  " % (tagged, total, pct)
              + ", ".join("%s=%d" % (k, counts[k])
                          for k in ("vendor", "title", "inline",
                                    "catalogue", "none")))
    if args.dry_run:
        print("\n  dry run -- nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
