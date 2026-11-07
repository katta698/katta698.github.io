#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate the Azure service catalogue the announcement tagger matches on.

    python scripts/refresh_azure_services.py

Why this exists
---------------
`refresh_aws_services.py` has generated 687 AWS names from botocore since
August. Azure and GCP got a hand-written stub on 17 August 2026 and nothing
has touched them since: 24 names and 27 names respectively. Measured
2026-11-07, that is a 28x vocabulary gap, and it does not show up as an
error anywhere -- it shows up as Microsoft apparently not shipping.

Two distinct failures come out of a thin catalogue, and both look like
findings about the cloud rather than defects in us:

  1. SERVICES GO UNRECOGNISED. `news_tag.py` falls back to pulling a phrase
     out of the headline when nothing in the catalogue matches, so the
     service is not missing from the store -- it is present under a name
     nobody would search for.
  2. ONE SERVICE FRAGMENTS. With no canonical name to collapse onto, the
     store ended up holding `Azure SQL`, `Azure SQL Database`, `Azure SQL
     DB` and `Azure SQL Managed Instance` as four separate tags, splitting
     one family's count four ways and pushing every one of them down the
     ranking.

The cost was visible the first time these numbers were put on a page:
Azure OpenAI read 0.0% of Microsoft's quarter. Microsoft plainly did not
stop shipping AI. Worse, the name itself was stale -- Azure OpenAI Service
is now Azure AI Foundry, which is exactly the drift a catalogue with no
refresh cannot survive.

Where the names come from
-------------------------
There is no botocore for Azure, so this takes the union of three sources
and keeps the existing file as a floor:

  * azure.microsoft.com/en-us/products/ -- Microsoft's own product
    directory. The page is server-rendered, so the product slugs are in the
    HTML. Display titles are NOT: every card's anchor text is the literal
    word "Product", so names are derived from the slug instead.
  * The Azure release communications feed, which tags each announcement
    with the product it concerns. These are real display names, in the exact
    form Microsoft writes them in announcements -- which is the form this
    catalogue has to match. It is also a short feed, so it supplements the
    directory rather than replacing it.
  * Whatever is already in azure_services.json. Never lose a curated name
    to a bad fetch.

The Azure Retail Prices API was tried first and rejected: it is the most
canonical source, but enumerating distinct serviceNames means paging the
whole SKU catalogue, and it timed out after two pages of a thousand. A
weekly job cannot depend on that.
"""
import io
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "scripts", "azure_services.json")

PRODUCTS_URL = "https://azure.microsoft.com/en-us/products/"
UPDATES_FEED = "https://www.microsoft.com/releasecommunications/api/v2/azure/rss"
UA = {"User-Agent": "Mozilla/5.0 (refresh_azure_services.py)"}

# The feed tags every item with its topic AND its status as well as its
# product, in one flat <category> list. These are the non-product ones.
# Listed rather than inferred, because "Storage" and "Identity" are both a
# topic here and a product elsewhere, and guessing gets that wrong.
FEED_TOPICS = {
    "Feature", "Features", "Launched", "In preview", "In development",
    "Retirements", "Security", "Services", "Management", "Compute",
    "Networking", "Databases", "Containers", "Storage", "Analytics",
    "DevOps", "Identity", "Integration", "Migration", "Media", "Mobile",
    "Web", "Windows", "Linux", "Open source", "SDK and Tools", "Pricing",
    "Regions & Datacenters", "Hybrid + multicloud", "Internet of Things",
    "AI + machine learning", "Management and governance", "Developer tools",
    "Mixed reality", "Blockchain", "Operating system", "Gallery", "Free",
}

# Azure product words that are also ordinary English. A bare mention of one
# of these is not evidence of the service, so the tagger requires a
# qualifier first -- same mechanism as ENGLISH_COLLISIONS in the AWS script,
# and for the same reason: "Config" once became the second biggest item on
# the blog index because 285 of its hits were the word "configuration".
ENGLISH_COLLISIONS = {
    "Advisor", "Automation", "Backup", "Batch", "Bastion", "Functions",
    "Monitor", "Search", "Storage", "Files", "Health", "Portal", "Updates",
    "Lighthouse", "Sentinel", "Purview", "Fabric", "Defender", "Firewall",
    "Compass", "Orbital", "Chaos Studio", "Load Testing", "Spring Apps",
    "Communication Services", "Notification Hubs", "Logic Apps", "Maps",
    "Migrate", "Marketplace", "Peering Service", "Quantum", "Site Recovery",
    "Virtual Desktop", "Confidential Ledger", "Data Share", "Dev Box",
}

# Slugs that are documentation or marketing surfaces rather than services.
SKIP_SLUGS = {
    "arm-templates", "category", "pricing", "free", "gallery", "products",
    "all-products", "windows", "linux", "open-source", "developer-tools",
}

# Derived names that are not an Azure service on their own, whatever the
# slug says. "local" is an adjective and "postgresql" is an engine three
# clouds host; both were tagging real announcements with the wrong thing.
SKIP_NAMES = {"Local", "PostgreSQL", "MySQL", "MariaDB", "Red", "OS", "DB"}

# Acronyms and words that must not be title-cased into something wrong when
# a name is derived from its slug.
ACRONYMS = {
    "ai": "AI", "api": "API", "sql": "SQL", "vm": "VM", "vms": "VMs",
    "iot": "IoT", "hpc": "HPC", "cdn": "CDN", "dns": "DNS", "vpn": "VPN",
    "nat": "NAT", "ddos": "DDoS", "hdinsight": "HDInsight", "devops": "DevOps",
    "sap": "SAP", "red": "Red", "os": "OS", "db": "DB", "ml": "ML",
    "cyclecloud": "CycleCloud", "postgresql": "PostgreSQL", "mysql": "MySQL",
    "mariadb": "MariaDB", "cosmos": "Cosmos", "netapp": "NetApp",
    "github": "GitHub", "openai": "OpenAI", "vmware": "VMware",
}


def fetch(url, cap=2_000_000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(cap).decode("utf-8", "replace")


def name_from_slug(slug):
    """'kubernetes-service' -> 'Kubernetes Service'.

    Deliberately NOT prefixed with 'Azure'. The tagger matches on word
    boundaries anywhere in the headline, so the unprefixed form matches both
    'Azure Kubernetes Service' and a bare 'Kubernetes Service', while the
    prefixed form would miss the second. The feed supplies the prefixed
    display names separately where Microsoft actually uses them.
    """
    parts = []
    for w in slug.split("-"):
        parts.append(ACRONYMS.get(w, w.capitalize()))
    return " ".join(parts)


def from_directory():
    try:
        html = fetch(PRODUCTS_URL)
    except Exception as exc:                                  # noqa: BLE001
        print("  product directory unreachable: %s" % exc)
        return {}
    slugs = set(re.findall(r"/en-us/products/([a-z0-9][a-z0-9\-]{2,60})/",
                           html))
    out = {}
    for s in sorted(slugs):
        if s in SKIP_SLUGS:
            continue
        nm = name_from_slug(s)
        if nm in SKIP_NAMES:
            continue
        out[nm] = "azure product directory"
        # BOTH forms, bare and prefixed. The tagger prefers the longest
        # matching name, so without "Azure Batch" in the catalogue a
        # headline reading "Azure Batch" is tagged with a bare "Batch" --
        # which is how the golden case for that announcement broke the
        # first time this ran. The bare form still earns its place: plenty
        # of headlines say "Kubernetes Service" with the brand elsewhere in
        # the sentence.
        if not nm.startswith(("Azure", "Microsoft")):
            out.setdefault("Azure " + nm, "azure product directory")
    print("  product directory: %d slug(s) -> %d name(s)" % (len(slugs),
                                                             len(out)))
    return out


def from_feed():
    try:
        xml = fetch(UPDATES_FEED)
    except Exception as exc:                                  # noqa: BLE001
        print("  updates feed unreachable: %s" % exc)
        return {}
    cats = [re.sub(r"<!\[CDATA\[|\]\]>", "", c).strip()
            for c in re.findall(r"<category[^>]*>(.*?)</category>", xml, re.S)]
    out = {}
    for c in cats:
        c = re.sub(r"\s+", " ", c).strip()
        if not c or c in FEED_TOPICS or len(c) < 3 or len(c) > 60:
            continue
        # A product category is one Microsoft brands. A bare topic word is
        # not, and the topic list above cannot be exhaustive.
        if not (c.startswith("Azure ") or c.startswith("Microsoft ")
                or "(" in c):
            continue
        out[c] = "azure updates feed"
        # 'Azure Kubernetes Service (AKS)' also yields the bare acronym and
        # the name without it -- both forms appear in announcements.
        m = re.match(r"^(.*?)\s*\(([A-Za-z0-9 ]{2,20})\)$", c)
        if m:
            out.setdefault(m.group(1).strip(), "azure updates feed")
            short = m.group(2).strip()
            if len(short) >= 3:
                out.setdefault(short, "azure updates feed")
    print("  updates feed: %d categor(ies) -> %d product name(s)"
          % (len(set(cats)), len(out)))
    return out


def existing():
    if not os.path.isfile(OUT):
        return {}, {}
    d = json.load(io.open(OUT, encoding="utf-8"))
    return d.get("services", {}), d


def main():
    print("Refreshing the Azure service catalogue")
    prior, prior_doc = existing()
    print("  existing file: %d name(s)" % len(prior))

    found = {}
    found.update(from_directory())
    found.update(from_feed())

    if len(found) < 40:
        # A thin result is what this script exists to prevent. Writing it
        # would quietly undo the fix on the next bad fetch.
        print("\n  REFUSING TO WRITE: only %d name(s) found, which is not a "
              "catalogue.\n  Both sources are probably unreachable. The "
              "existing file is left alone." % len(found))
        return 1

    services = {}
    for name, meta in prior.items():
        services[name] = (dict(meta) if isinstance(meta, dict)
                          else {"ambiguous": False})
        services[name].setdefault("source", "curated")
    for name, src in found.items():
        if name in services:
            continue
        # A ONE-WORD name always needs a qualifier, whatever it is.
        #
        # Deriving names from slugs turns `local` into "Local", `postgresql`
        # into "PostgreSQL" and `github` into "GitHub", and the first run
        # duly tagged announcements with all three. None of them is evidence
        # of an Azure service on its own: "local" is an adjective,
        # "PostgreSQL" is an engine three clouds host, and GitHub is not
        # Azure. Marking every single-word name ambiguous makes the tagger
        # demand an "Azure"/"Microsoft" voucher before it counts, which is
        # the same mechanism the AWS catalogue uses for "Config" -- a word
        # that once became the second largest item on the blog index
        # because 285 of its hits were "configuration".
        # An ACRONYM is exempt. The first cut marked every one-word name
        # ambiguous and that cost the single biggest win: "AKS" needs no
        # voucher -- nobody writes it meaning anything else -- but headlines
        # like "AKS Release 2026-10-25" carry no "Azure", so requiring one
        # dropped 25 correctly tagged announcements back to untagged.
        # Lower-case English is the risk; capitals are not.
        acronym = name.isupper() and len(name) >= 2
        single = " " not in name and not acronym
        services[name] = {"ambiguous": single or name in ENGLISH_COLLISIONS,
                          "source": src}

    payload = {
        "_comment": [
            "Generated by scripts/refresh_azure_services.py. Do not edit by",
            "hand -- re-run the script instead. Names curated before",
            "2026-11-07 are kept and marked source=curated.",
        ],
        "count": len(services),
        "services": services,
    }
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write("\n")

    added = len(services) - len(prior)
    print("\nwrote %s" % OUT)
    print("  %d name(s), %d new, %d need a qualifier before a bare mention "
          "counts" % (len(services), added,
                      sum(1 for v in services.values()
                          if v.get("ambiguous"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
