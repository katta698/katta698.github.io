#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate the AWS service catalogue used by the blog's sidebar widgets.

    python scripts/refresh_aws_services.py

Writes scripts/aws_services.json from botocore's own service models, which are
AWS's published API definitions -- 425 services and counting. That is the point:
the list of AWS services is AWS's to maintain, not this repo's.

Why a cached file rather than reading botocore during every sync: parsing all
425 service models takes about seven seconds, and sync_blog.py runs on every
publish. The cache reads in milliseconds.

Why not detect services from the prose instead: that was tried. A capitalised
word after the token "AWS" is not evidence of a service, and the widget ended
up with bubbles labelled "What", "They" and "Terraform". AWS's own catalogue
has no such problem.

Keeping it current needs no human: .github/workflows/refresh-aws-services.yml
upgrades botocore weekly, runs this, and commits the result if it changed. A
service launched at re:Invent appears on the site the week botocore ships it.
"""
import concurrent.futures
import gzip
import json
import os
import re
import sys
import urllib.request

try:
    import botocore
except ImportError:
    print("botocore is not installed. pip install botocore")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "scripts", "aws_services.json")

# Service names that are also ordinary English words. These are the only names
# that need a qualifier ("AWS Config", "Amazon Connect") before a bare mention
# counts, and unlike the service list itself this one is stable -- English does
# not add words the way AWS adds services.
#
# It exists because counting bare mentions made "Config" the second largest
# item on the blog index: 285 of its 426 hits were "configuration".
ENGLISH_COLLISIONS = {
    "Config", "Connect", "Backup", "Batch", "Shield", "Glue", "Health",
    "Support", "Detective", "Inspector", "Forecast", "Translate", "Transcribe",
    "Comprehend", "Personalize", "Location", "Budgets", "Signer", "Scheduler",
    "Proton", "Chime", "Outposts", "Organizations", "Artifact", "Braket",
    "Compute Optimizer", "Resource Explorer", "Application Auto Scaling",
    "Discovery", "Entity Resolution", "Payment Cryptography", "Private CA",
    "Pricing", "Marketplace", "Directory", "Notifications", "Recycle Bin",
    "Snowball", "Snow Device Management", "Timestream Query", "Panorama",
    "Deadline", "Omics", "One", "Q", "Rekognition", "Polly", "Kendra",
}

# Names botocore produces that are too generic to match safely in prose, or
# that describe an API surface rather than something anyone writes about.
SKIP = {
    "Service", "API", "APIs", "Data", "Runtime", "Control", "Plane", "Admin",
    "Management", "Core", "Simple Storage", "Elastic Compute Cloud",
    "Simple Queue", "Simple Notification", "Simple Email", "Web Services",
    "Elastic Load Balancing v2", "Elastic Load Balancing v3", "SFN",
}

PREFIX_RE = re.compile(r"^(?:AWS|Amazon)\s+")
SUFFIX_RE = re.compile(r"\s+(?:Service|Services|API|Runtime|Control Plane)$")


def clean(name):
    if not name:
        return None
    name = PREFIX_RE.sub("", name.strip())
    name = SUFFIX_RE.sub("", name).strip()
    if len(name) < 2 or name in SKIP:
        return None
    return name



# ── Descriptions and links ────────────────────────────────────
# The one-line description shown on hover comes from AWS's own product page
# meta description, and the page itself is the "read more" link. Two reasons
# for that source rather than botocore's `documentation` field: botocore's text
# is an API reference introduction rather than a description of the service
# ("Describes the API operations for ... Bedrock models"), and for the biggest
# services -- S3, VPC, ALB, Aurora, Security Hub -- it is simply empty. The
# product pages are server-rendered, so the description is in the HTML.
#
# Most URLs derive from the service name. service_links.json holds only the
# ones that do not, and it stays small on purpose: the derived path is what
# makes this automatic for the majority.
PRODUCT_URL = "https://aws.amazon.com/%s/"
UA = {"User-Agent": "Mozilla/5.0 (refresh_aws_services.py)"}
META_RE = re.compile(r'<meta name="description" content="([^"]{40,400})"')


def _slug_candidates(name, links):
    override = links.get("slugs", {}).get(name)
    if override:
        return [override]
    base = name.lower().replace(" ", "-").replace(".", "")
    return list(dict.fromkeys([base, base.replace("-", "")]))


def fetch_description(args):
    """Return (name, url, description) using AWS's own page text, or Nones."""
    name, links = args
    for slug in _slug_candidates(name, links):
        url = PRODUCT_URL % slug
        try:
            req = urllib.request.Request(url, headers=UA)
            html = urllib.request.urlopen(req, timeout=20).read(80000)
        except Exception:
            continue
        m = META_RE.search(html.decode("utf-8", "replace"))
        if not m:
            continue
        desc = re.sub(r"\s+", " ", m.group(1)).strip()
        # A page that describes the whole cloud rather than one service is a
        # redirect to a landing page, not the service's own page.
        if "Amazon Web Services" in desc and name not in desc:
            continue
        return name, url, desc
    return name, None, None


def add_descriptions(services, only=None):
    links_path = os.path.join(ROOT, "scripts", "service_links.json")
    links = {}
    if os.path.isfile(links_path):
        links = json.load(open(links_path, encoding="utf-8"))
    skip = set(links.get("skip", {}).get("names", []))

    # Names AWS does not publish as their own API but that people write about.
    for extra in links.get("extra", {}).get("names", []):
        services.setdefault(extra, {"ambiguous": extra in ENGLISH_COLLISIONS,
                                    "source": None})

    targets = [n for n in services if n not in skip]
    if only:
        targets = [n for n in targets if n in only]

    print(f"  fetching descriptions for {len(targets)} services...")
    resolved = 0
    with concurrent.futures.ThreadPoolExecutor(12) as ex:
        for name, url, desc in ex.map(fetch_description,
                                      ((n, links) for n in targets)):
            if url:
                services[name]["url"] = url
                services[name]["desc"] = desc
                resolved += 1
    print(f"  {resolved} of {len(targets)} have an AWS description and link")
    missing = [n for n in targets if "url" not in services[n]]
    if missing:
        print("  no product page resolved for: " + ", ".join(sorted(missing)[:15]))
    return services


def main():
    data_dir = os.path.join(os.path.dirname(botocore.__file__), "data")
    services = {}

    for entry in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, entry)
        if not os.path.isdir(path):
            continue
        versions = sorted(os.listdir(path))
        if not versions:
            continue
        meta = None
        for fn in ("service-2.json.gz", "service-2.json"):
            f = os.path.join(path, versions[-1], fn)
            if not os.path.exists(f):
                continue
            opener = gzip.open if fn.endswith(".gz") else open
            try:
                with opener(f, "rt", encoding="utf-8") as fh:
                    meta = json.load(fh).get("metadata", {})
            except Exception:
                meta = None
            break
        if not meta:
            continue

        # Three spellings per service, because prose uses all of them: "S3",
        # "Amazon S3" and "Simple Storage Service" are the same thing, and a
        # post might use any. Longest first so "Step Functions" is preferred
        # over a bare "SFN" that nobody writes.
        candidates = {clean(meta.get("serviceId")),
                      clean(meta.get("serviceAbbreviation")),
                      clean(meta.get("serviceFullName"))}
        for name in sorted(filter(None, candidates), key=len, reverse=True):
            if name not in services:
                services[name] = {
                    "ambiguous": name in ENGLISH_COLLISIONS,
                    "source": entry,
                }

    # Only the services this blog actually writes about get a description --
    # fetching all 690 would mean 690 requests to AWS every week for pages
    # nobody will hover over.
    wanted = os.environ.get("DESCRIBE_SERVICES")
    only = set(wanted.split(",")) if wanted else None
    services = add_descriptions(services, only=only)

    payload = {
        "_comment": ("Generated by scripts/refresh_aws_services.py from "
                     "botocore's service models. Do not edit by hand -- "
                     "re-run the script instead."),
        "botocore_version": botocore.__version__,
        "count": len(services),
        "services": services,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"wrote {OUT}")
    print(f"  {len(services)} names from botocore {botocore.__version__}")
    print(f"  {sum(1 for v in services.values() if v['ambiguous'])} need a "
          f"qualifier before bare mentions count")
    return 0


if __name__ == "__main__":
    sys.exit(main())
