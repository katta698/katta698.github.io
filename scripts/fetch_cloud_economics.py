#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What the three clouds actually disclose about themselves, from SEC filings.

    python scripts/fetch_cloud_economics.py

Every figure here comes from a company's own 10-Q or 10-K, parsed out of the
XBRL instance the filing ships. Nothing is an analyst estimate and nothing is
scraped from a press article quoting one.

Why the XBRL instance and not the easy API
------------------------------------------
data.sec.gov's companyconcept and companyfacts endpoints return only
CONSOLIDATED values -- they strip the dimensions. Asking them for Amazon's
revenue gives the whole company, retail included, which is not the question.
Segment figures live on the business-segment axis inside the filing's own
instance document, so that is what this reads:

    us-gaap:StatementBusinessSegmentsAxis
      -> amzn:AmazonWebServicesSegmentMember
      -> goog:GoogleCloudMember

A context carrying exactly one member, that member, is an AWS-only or
Cloud-only fact. Contexts carrying several members are roll-ups and are
skipped, which is why the member list is compared for equality rather than
membership.

The asymmetry, which is the point of the whole page
---------------------------------------------------
Amazon tags AWS revenue AND operating income directly.
Alphabet tags Google Cloud revenue and the segment's total costs, so
operating income is the subtraction -- marked as derived, with both inputs
kept so it can be checked.
Microsoft discloses NEITHER for Azure.

Microsoft's 10-K says "Azure and other cloud services revenue increased 41%"
-- a growth rate, against an undisclosed base. Its "Microsoft Cloud revenue"
figure is a different thing again: it bundles Office 365, Dynamics and
LinkedIn, so it is not comparable to AWS and must never be presented as if
it were.

So a like-for-like three-way revenue table CANNOT be built from public
filings. Every "Azure has N% of the market" figure in circulation is an
analyst estimate. This file records the gap as a gap -- `disclosed: false`
-- rather than filling it, and the page says so in words.

Rate limits: the SEC asks for a descriptive User-Agent and no more than ten
requests a second. This makes about six requests in total and sleeps between
them, which is far inside that.
"""
import io
import json
import os
import re
import sys
import time
import datetime as dt
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "intelligence", "cloud-economics.json")

UA = ("jayanthkatta.com cloud-economics research; contact "
      "katta.jayant@gmail.com")
X = "{http://www.xbrl.org/2003/instance}"

# (label, CIK, segment member, what the member is called in prose)
COMPANIES = [
    ("AWS", "Amazon", "0001018724", "amzn:AmazonWebServicesSegmentMember"),
    ("Google Cloud", "Alphabet", "0001652044", "goog:GoogleCloudMember"),
]
MICROSOFT = ("Azure", "Microsoft", "0000789019")

CONCEPTS = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "OperatingIncomeLoss": "operating_income",
    # Alphabet does not tag OperatingIncomeLoss on the Google Cloud member --
    # it tags the segment's total costs instead. Revenue minus costs is the
    # same figure its own segment table prints, so it is derived rather than
    # left blank, and marked `derived` with both inputs kept so the
    # subtraction can be checked. Amazon tags OperatingIncomeLoss directly
    # and is never derived.
    "CostsAndExpenses": "costs",
}


def get(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for n in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=90).read()
        except Exception:                                   # noqa: BLE001
            if n == tries - 1:
                raise
            time.sleep(2 * (n + 1))


def latest_filing(cik):
    """The most recent 10-Q or 10-K, and the XBRL instance inside it."""
    sub = json.loads(get("https://data.sec.gov/submissions/CIK%s.json" % cik))
    recent = sub["filings"]["recent"]
    for i, form in enumerate(recent["form"]):
        if form not in ("10-Q", "10-K"):
            continue
        acc = recent["accessionNumber"][i]
        bare = acc.replace("-", "")
        base = ("https://www.sec.gov/Archives/edgar/data/%d/%s"
                % (int(cik), bare))
        time.sleep(0.3)
        idx = json.loads(get(base + "/index.json"))
        inst = [f["name"] for f in idx["directory"]["item"]
                if f["name"].endswith("_htm.xml")]
        if not inst:
            continue
        return {"form": form, "filed": recent["filingDate"][i],
                "accession": acc, "instance": base + "/" + inst[0],
                "primary": base + "/" + recent["primaryDocument"][i]}
    return None


def days_between(a, b):
    f = lambda s: dt.date(*[int(x) for x in s.split("-")])    # noqa: E731
    return (f(b) - f(a)).days


def segment_facts(instance_url, member):
    """Quarterly revenue and operating income for one reportable segment.

    Only contexts whose ENTIRE dimension set is this one member count. A
    context carrying two members is a roll-up -- Amazon files a combined
    "North America and International" one -- and including those would
    double-count.
    """
    root = ET.fromstring(get(instance_url))
    ctx = {}
    for c in root.iter(X + "context"):
        members = [e.text.strip() for e in c.iter()
                   if e.tag.endswith("explicitMember") and e.text]
        if members != [member]:
            continue
        per = c.find(X + "period")
        start = per.findtext(X + "startDate")
        end = per.findtext(X + "endDate")
        if start and end:
            ctx[c.get("id")] = (start, end)

    found = {}
    for el in root:
        tag = el.tag.split("}")[-1]
        if tag not in CONCEPTS or el.get("contextRef") not in ctx:
            continue
        start, end = ctx[el.get("contextRef")]
        span = days_between(start, end)
        # A quarter, not a half-year or a full year. Filings carry both.
        if not 80 <= span <= 100:
            continue
        try:
            val = int(el.text)
        except (TypeError, ValueError):
            continue
        found.setdefault(CONCEPTS[tag], {})[end] = {
            "start": start, "end": end, "days": span, "usd": val}
    return found


def azure_growth(primary_url):
    """Microsoft's Azure line: a growth rate against an undisclosed base.

    Deliberately returns the SENTENCE as well as the number. The number on
    its own invites being put in a column beside two dollar figures, which
    is exactly the comparison the filing does not support.
    """
    html = get(primary_url).decode("utf-8", "replace")
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    m = re.search(r"(Azure and other cloud services revenue "
                  r"(?:increased|grew)\s+(\d+)%[^.]{0,60}\.)", text, re.I)
    if not m:
        return None
    return {"sentence": m.group(1).strip(), "growth_pct": int(m.group(2))}


def main():
    out = {
        "captured": dt.date.today().isoformat(),
        "source": "SEC EDGAR -- each company's own 10-Q/10-K XBRL instance",
        "note": ("Microsoft does not disclose Azure revenue or operating "
                 "income. It reports a growth rate against an undisclosed "
                 "base. A like-for-like three-way comparison is therefore "
                 "not possible from public filings."),
        "clouds": {},
    }

    for label, company, cik, member in COMPANIES:
        print("  %s (%s)" % (label, company))
        f = latest_filing(cik)
        if not f:
            print("     no filing with an XBRL instance found")
            continue
        print("     %s filed %s" % (f["form"], f["filed"]))
        facts = segment_facts(f["instance"], member)
        quarters = {}
        for metric, byend in facts.items():
            for end, row in byend.items():
                quarters.setdefault(end, {})[metric] = row["usd"]
                quarters[end]["start"] = row["start"]
        # Fill operating income by subtraction only where it was not tagged,
        # and say so in the record rather than silently presenting a derived
        # figure as a reported one.
        for end, q in quarters.items():
            if "operating_income" not in q and {"revenue", "costs"} <= set(q):
                q["operating_income"] = q["revenue"] - q["costs"]
                q["operating_income_derived"] = True
                q["operating_income_working"] = (
                    "revenue %d - costs and expenses %d"
                    % (q["revenue"], q["costs"]))
        out["clouds"][label] = {
            "company": company, "cik": cik, "disclosed": True,
            "form": f["form"], "filed": f["filed"],
            "accession": f["accession"],
            "quarters": quarters,
        }
        for end in sorted(quarters)[-2:]:
            q = quarters[end]
            print("     %s  revenue $%s  operating $%s"
                  % (end,
                     "{:,}".format(q.get("revenue", 0)),
                     "{:,}".format(q.get("operating_income", 0))))
        time.sleep(0.4)

    label, company, cik = MICROSOFT
    print("  %s (%s)" % (label, company))
    f = latest_filing(cik)
    g = azure_growth(f["primary"]) if f else None
    out["clouds"][label] = {
        "company": company, "cik": cik, "disclosed": False,
        "form": f["form"] if f else None,
        "filed": f["filed"] if f else None,
        "accession": f["accession"] if f else None,
        "growth": g,
        "why": ("Microsoft reports Azure as a growth rate only. Its "
                "'Microsoft Cloud' figure bundles Office 365, Dynamics and "
                "LinkedIn and is not comparable to AWS or Google Cloud."),
    }
    if g:
        print("     %s" % g["sentence"][:96])
    else:
        print("     no Azure growth sentence found in the filing")

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("  -> intelligence/cloud-economics.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
