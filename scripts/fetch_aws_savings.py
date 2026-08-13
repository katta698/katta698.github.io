#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch real Reserved Instance, Savings Plan and Spot rates.

    python scripts/fetch_aws_savings.py <out.json>

The EC2 estimator used to show four hardcoded discount percentages -- 28% for
a Savings Plan, 40% and 60% for Reserved, 70% for Spot -- applied to every
instance in every region. Those are ballpark figures from AWS marketing pages,
and the real discount varies enormously: a 3-year all-upfront RI on a t3.micro
is a different number from one on an r5.4xlarge, and Spot moves hourly.

Three sources, because AWS models them as three different products:

  Reserved      the same Price List SKU as On-Demand, under terms.Reserved
  Savings Plan  its own API, savingsplans describe-savings-plans-offering-rates
  Spot          ec2 describe-spot-price-history, a live market price

Spot is stored with the timestamp AWS gave it. It is a market rate, not a
tariff, and presenting last week's number as today's is the kind of claim
this repo has already been burned by once.
"""
import concurrent.futures as cf
import json
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TYPES = ["t3.micro", "t3.small", "t3.medium", "t3.large",
         "m5.large", "m5.xlarge", "m5.2xlarge", "m5.4xlarge",
         "c5.large", "c5.xlarge", "c5.2xlarge", "c5.4xlarge",
         "r5.large", "r5.xlarge", "r5.2xlarge", "r5.4xlarge",
         "i3.large", "i3.xlarge"]

REGIONS = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "EU (Ireland)",
    "eu-central-1": "EU (Frankfurt)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
    "ap-south-1": "Asia Pacific (Mumbai)",
}

# Only Linux and Windows: RHEL and SUSE add a licence charge that is not
# discounted by a reservation, so blending them into one rate would misstate
# both. The estimator falls back to showing no discount for those.
OSES = ["Linux", "Windows"]

HOURS_1YR = 8760
HOURS_3YR = 26280


def aws_json(args, timeout=120):
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if out.returncode != 0 or not out.stdout.strip():
            return None
        return json.loads(out.stdout)
    except Exception:
        return None


def reserved(job):
    """Effective hourly rate for the three RI shapes the estimator shows."""
    region, location, itype, os_name = job
    doc = aws_json([
        "aws", "pricing", "get-products", "--region", "us-east-1",
        "--service-code", "AmazonEC2", "--no-cli-pager", "--max-results", "1",
        "--output", "json", "--filters",
        "Type=TERM_MATCH,Field=instanceType,Value=" + itype,
        "Type=TERM_MATCH,Field=location,Value=" + location,
        "Type=TERM_MATCH,Field=operatingSystem,Value=" + os_name,
        "Type=TERM_MATCH,Field=tenancy,Value=Shared",
        "Type=TERM_MATCH,Field=preInstalledSw,Value=NA",
        "Type=TERM_MATCH,Field=capacitystatus,Value=Used",
        "Type=TERM_MATCH,Field=licenseModel,Value=No License required",
    ])
    if not doc or not doc.get("PriceList"):
        return region, itype, os_name, {}

    raw = doc["PriceList"][0]
    p = json.loads(raw) if isinstance(raw, str) else raw
    out = {}
    for term in p.get("terms", {}).get("Reserved", {}).values():
        a = term.get("termAttributes", {})
        if a.get("OfferingClass") != "standard":
            continue
        years = a.get("LeaseContractLength")          # "1yr" / "3yr"
        option = a.get("PurchaseOption")              # "No Upfront" / "All Upfront" / ...
        upfront = 0.0
        hourly = 0.0
        for dim in term.get("priceDimensions", {}).values():
            usd = float(dim["pricePerUnit"]["USD"])
            if dim.get("unit") == "Quantity":
                upfront = usd
            else:
                hourly = usd
        span = HOURS_1YR if years == "1yr" else HOURS_3YR
        effective = hourly + (upfront / span if upfront else 0.0)
        if effective <= 0:
            continue
        key = None
        if years == "1yr" and option == "No Upfront":
            key = "ri1yNoUp"
        elif years == "1yr" and option == "All Upfront":
            key = "ri1yAllUp"
        elif years == "3yr" and option == "All Upfront":
            key = "ri3yAllUp"
        if key:
            out[key] = round(effective, 6)
    return region, itype, os_name, out


def savings_plan(job):
    """Compute Savings Plan rate: 1-year, no upfront, per instance type."""
    region, itype = job
    doc = aws_json([
        "aws", "savingsplans", "describe-savings-plans-offering-rates",
        "--region", "us-east-1", "--no-cli-pager", "--max-results", "20",
        "--output", "json",
        "--service-codes", "AmazonEC2",
        "--filters",
        "name=region,values=" + region,
        "name=instanceType,values=" + itype,
        "name=tenancy,values=shared",
        "name=productDescription,values=Linux/UNIX",
    ])
    if not doc:
        return region, itype, None
    best = None
    for r in doc.get("searchResults", []):
        prod = r.get("savingsPlanOffering", {})
        if prod.get("planType") != "Compute":
            continue
        if prod.get("durationSeconds") != 31536000:      # 1 year
            continue
        if prod.get("paymentOption") != "No Upfront":
            continue
        rate = float(r.get("rate", 0))
        if rate > 0 and (best is None or rate < best):
            best = rate
    return region, itype, (round(best, 6) if best else None)


def spot(region):
    """Current Linux spot price per type, with the timestamp AWS reported."""
    doc = aws_json([
        "aws", "ec2", "describe-spot-price-history", "--region", region,
        "--no-cli-pager", "--output", "json",
        "--product-descriptions", "Linux/UNIX",
        "--instance-types"] + TYPES + [
        "--max-items", "400",
    ], timeout=180)
    if not doc:
        return region, {}
    # Latest quote per (type, AZ) first, then the cheapest AZ. Taking the
    # cheapest row across the whole returned history instead finds an old dip:
    # the first run here surfaced a price from seven weeks earlier and labelled
    # it current, which the timestamp on screen is what caught.
    newest = {}
    for h in doc.get("SpotPriceHistory", []):
        key = (h["InstanceType"], h["AvailabilityZone"])
        if key not in newest or h["Timestamp"] > newest[key]["Timestamp"]:
            newest[key] = h
    latest = {}
    for (itype, _az), h in newest.items():
        usd = float(h["SpotPrice"])
        if itype not in latest or usd < latest[itype]["usd"]:
            latest[itype] = {"usd": round(usd, 6), "at": h["Timestamp"]}
    return region, latest


if __name__ == "__main__":
    ri_jobs = [(r, loc, t, o) for r, loc in REGIONS.items()
               for t in TYPES for o in OSES]
    sp_jobs = [(r, t) for r in REGIONS for t in TYPES]

    print("reserved: %d, savings plans: %d, spot: %d regions"
          % (len(ri_jobs), len(sp_jobs), len(REGIONS)))

    ri, sp, sptable = {}, {}, {}
    with cf.ThreadPoolExecutor(16) as ex:
        for region, itype, os_name, rates in ex.map(reserved, ri_jobs):
            if rates:
                ri.setdefault(region, {}).setdefault(itype, {})[os_name] = rates
        for region, itype, rate in ex.map(savings_plan, sp_jobs):
            if rate:
                sp.setdefault(region, {})[itype] = rate
        for region, table in ex.map(spot, REGIONS):
            if table:
                sptable[region] = table

    print("reserved resolved: %d" % sum(len(v) for r in ri.values() for v in r.values()))
    print("savings plans:     %d" % sum(len(v) for v in sp.values()))
    print("spot:              %d" % sum(len(v) for v in sptable.values()))

    json.dump({"reserved": ri, "savingsPlan": sp, "spot": sptable},
              open(sys.argv[1], "w", encoding="utf-8"), indent=1, sort_keys=True)
    print("wrote", sys.argv[1])
