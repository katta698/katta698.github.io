"""Fetch real EC2 and EBS prices from AWS's Price List API.

Two things this fixes in the site's estimator:

1. The region/OS multiplier model. Windows is licensed per vCPU, so its
   premium over Linux grows with instance size -- no single multiplier fits
   both t3.micro and m5.4xlarge. Same for regions: the gap between us-east-1
   and ap-south-1 is not a constant across families.

2. The licenseModel trap. Asking for operatingSystem=Windows returns three
   SKUs -- "Bring your own license" and "License Included - Infrastructure"
   both price at the Linux rate, and only "No License required" carries the
   Windows licence. Taking the first match reports Windows as costing the
   same as Linux, which is what a naive fetch does.
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

OSES = ["Linux", "Windows", "RHEL", "SUSE"]

# volumeApiName -> label shown in the UI
EBS_VOLUMES = {
    "gp3": "gp3 (General Purpose SSD)",
    "gp2": "gp2 (General Purpose SSD, previous gen)",
    "io2": "io2 (Provisioned IOPS SSD)",
    "io1": "io1 (Provisioned IOPS SSD, previous gen)",
    "st1": "st1 (Throughput Optimized HDD)",
    "sc1": "sc1 (Cold HDD)",
    "standard": "standard (Magnetic, legacy)",
}


def _run(filters, max_results="10"):
    cmd = ["aws", "pricing", "get-products", "--region", "us-east-1",
           "--service-code", "AmazonEC2", "--no-cli-pager",
           "--max-results", max_results, "--output", "json", "--filters"] + filters
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            return []
        items = json.loads(out.stdout).get("PriceList", [])
        return [json.loads(i) if isinstance(i, str) else i for i in items]
    except Exception:
        return []


def _first_usd(doc):
    for term in doc["terms"]["OnDemand"].values():
        for dim in term["priceDimensions"].values():
            usd = float(dim["pricePerUnit"]["USD"])
            if usd > 0:
                return usd
    return None


def instance_price(job):
    region, location, itype, os_name = job
    docs = _run([
        "Type=TERM_MATCH,Field=instanceType,Value=" + itype,
        "Type=TERM_MATCH,Field=location,Value=" + location,
        "Type=TERM_MATCH,Field=operatingSystem,Value=" + os_name,
        "Type=TERM_MATCH,Field=tenancy,Value=Shared",
        "Type=TERM_MATCH,Field=preInstalledSw,Value=NA",
        "Type=TERM_MATCH,Field=capacitystatus,Value=Used",
        # The one that matters: licence included, not BYOL.
        "Type=TERM_MATCH,Field=licenseModel,Value=No License required",
    ])
    for d in docs:
        usd = _first_usd(d)
        if usd:
            return region, itype, os_name, usd
    return region, itype, os_name, None


def ebs_price(job):
    region, location, vol = job
    docs = _run([
        "Type=TERM_MATCH,Field=location,Value=" + location,
        "Type=TERM_MATCH,Field=productFamily,Value=Storage",
        "Type=TERM_MATCH,Field=volumeApiName,Value=" + vol,
    ])
    for d in docs:
        usd = _first_usd(d)
        if usd:
            return region, vol, "storage", usd
    return region, vol, "storage", None


def ebs_extra(job):
    """gp3/io1/io2 charge separately for provisioned IOPS and throughput."""
    region, location, vol, family, group = job
    filters = [
        "Type=TERM_MATCH,Field=location,Value=" + location,
        "Type=TERM_MATCH,Field=productFamily,Value=" + family,
        "Type=TERM_MATCH,Field=volumeApiName,Value=" + vol,
    ]
    if group:
        filters.append("Type=TERM_MATCH,Field=groupDescription,Value=" + group)
    for d in _run(filters):
        usd = _first_usd(d)
        if usd:
            return region, vol, family, usd
    return region, vol, family, None


ec2_jobs = [(r, loc, t, o) for r, loc in REGIONS.items()
            for t in TYPES for o in OSES]
ebs_jobs = [(r, loc, v) for r, loc in REGIONS.items() for v in EBS_VOLUMES]
extra_jobs = ([(r, loc, v, "System Operation", None)
               for r, loc in REGIONS.items() for v in ("gp3", "io1", "io2")] +
              [(r, loc, "gp3", "Provisioned Throughput", None)
               for r, loc in REGIONS.items()])

print("fetching %d instance prices, %d volume prices, %d IOPS/throughput..."
      % (len(ec2_jobs), len(ebs_jobs), len(extra_jobs)))

ec2, ebs, miss = {}, {}, []
with cf.ThreadPoolExecutor(16) as ex:
    for region, itype, os_name, usd in ex.map(instance_price, ec2_jobs):
        if usd is None:
            miss.append("ec2 %s/%s/%s" % (region, itype, os_name))
        else:
            ec2.setdefault(region, {}).setdefault(itype, {})[os_name] = round(usd, 6)
    for region, vol, _k, usd in ex.map(ebs_price, ebs_jobs):
        if usd is None:
            miss.append("ebs %s/%s" % (region, vol))
        else:
            ebs.setdefault(region, {}).setdefault(vol, {})["gb"] = round(usd, 6)
    for region, vol, family, usd in ex.map(ebs_extra, extra_jobs):
        if usd is None:
            continue
        key = "iops" if family == "System Operation" else "throughput"
        ebs.setdefault(region, {}).setdefault(vol, {})[key] = round(usd, 6)

print("instances resolved: %d" % sum(len(v) for r in ec2.values() for v in r.values()))
print("volumes resolved:   %d" % sum(len(v) for r in ebs.values() for v in r.values()))
if miss:
    print("missing (%d): %s" % (len(miss), ", ".join(miss[:10])))

json.dump({"ec2": ec2, "ebs": ebs, "labels": EBS_VOLUMES},
          open(sys.argv[1], "w", encoding="utf-8"), indent=1, sort_keys=True)
print("wrote", sys.argv[1])

u = ec2.get("us-east-1", {})
print("\nWindows premium over Linux, us-east-1 (the tool assumed a flat 1.35x):")
for t in ["t3.micro", "m5.large", "m5.4xlarge", "r5.4xlarge"]:
    d = u.get(t, {})
    if d.get("Linux") and d.get("Windows"):
        print("  %-11s Linux %-9s Windows %-9s = %.2fx"
              % (t, d["Linux"], d["Windows"], d["Windows"] / d["Linux"]))

print("\nRegion premium over us-east-1 for m5.large Linux (tool assumed one constant per region):")
base = ec2.get("us-east-1", {}).get("m5.large", {}).get("Linux")
for r in REGIONS:
    v = ec2.get(r, {}).get("m5.large", {}).get("Linux")
    if v and base:
        print("  %-16s %-9s = %.3fx" % (r, v, v / base))
