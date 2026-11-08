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
# The reportable segment Azure sits INSIDE. Microsoft does tag this one, so
# there is a real audited number here -- but it also contains Windows Server,
# SQL Server, Visual Studio and Enterprise Services, so it is an upper bound
# on Azure and not a measure of it. Captured because "we cannot know anything
# about Azure's size" would be a worse answer than "here is the ceiling".
# Microsoft renames its reportable segments, so this is a LIST and the
# fetcher records what it actually found.
#
# It was a single hardcoded "msft:IntelligentCloudMember" until 2026-11-08.
# Microsoft had by then reorganised into two reportable segments -- Agents
# and Infra, and Devices and Consumer -- and Intelligent Cloud no longer
# existed in the filing. Nothing failed. `enclosing_segment` simply came
# back null, the page printed no ceiling for Azure, and the omission looked
# exactly like Microsoft disclosing even less than before.
#
# Newest first. Older names are kept so a re-run over an archived filing
# still resolves.
MSFT_SEGMENT_CANDIDATES = [
    ("msft:AgentsAndInfraMember", "Agents and Infra"),
    ("msft:IntelligentCloudMember", "Intelligent Cloud"),
]

SEGMENT_AXIS = "StatementBusinessSegmentsAxis"


def segment_members(instance_url):
    """Every reportable-segment member the filing actually tags.

    Recorded whether or not a candidate matches, so a rename is visible in
    the data instead of arriving as a silent null.
    """
    root = ET.fromstring(get(instance_url))
    out = set()
    for c in root.iter(X + "context"):
        for e in c.iter():
            if not e.tag.endswith("explicitMember"):
                continue
            if SEGMENT_AXIS in (e.get("dimension") or "") and e.text:
                out.add(e.text.strip())
    return sorted(out)

# Members that qualify a segment rather than naming another one. A context
# carrying one of these alongside the segment member is still that segment.
QUALIFIER_MEMBERS = {
    "us-gaap:OperatingSegmentsMember",
    "us-gaap:ReportableSegmentsMember",
    "us-gaap:ReportableSubsegmentsMember",
}

CONCEPTS = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "OperatingIncomeLoss": "operating_income",
    # Costs are kept so operating income can be derived for a filer that
    # tags segment expenses but not segment operating income. Alphabet DOES
    # tag it -- see segment_facts on the two-member context that used to
    # hide it -- so nothing is derived today. The fallback stays because a
    # filer that stops tagging it should degrade to a checkable subtraction
    # rather than to a blank.
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

    A context counts when its members are this segment, plus at most the
    qualifier members below.

    The first rule here was "the entire dimension set must be this one
    member", written to reject Amazon's combined "North America and
    International" roll-up. It also silently threw away Alphabet's
    operating income, which is tagged on TWO members --
    us-gaap:OperatingSegmentsMember together with goog:GoogleCloudMember.
    So the figure was absent, the caller derived it from revenue minus
    costs, and the page apologised for an inference it never needed to
    make. The derived value happened to equal the reported one to the
    dollar, which is exactly why nobody noticed.

    A qualifier says what KIND of thing the segment is. It does not add a
    second entity, so it cannot double-count. Two real segment members
    still do, and are still rejected.
    """
    root = ET.fromstring(get(instance_url))
    ctx = {}
    for c in root.iter(X + "context"):
        members = [e.text.strip() for e in c.iter()
                   if e.tag.endswith("explicitMember") and e.text]
        if member not in members:
            continue
        if [m for m in members if m != member and m not in QUALIFIER_MEMBERS]:
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


def segment_facts_any(instance_url, member):
    """Like segment_facts, but keeps whatever period the filing reports.

    segment_facts() throws away anything that is not a quarter, which is
    right for comparing AWS with Google Cloud. Microsoft's latest filing is
    typically its 10-K, so insisting on a quarter would return nothing at
    all. The span is kept so the caller can say "year" rather than implying
    these are the same shape of number.
    """
    root = ET.fromstring(get(instance_url))
    ctx = {}
    for c in root.iter(X + "context"):
        members = [e.text.strip() for e in c.iter()
                   if e.tag.endswith("explicitMember") and e.text]
        if member not in members:
            continue
        if [m for m in members if m != member and m not in QUALIFIER_MEMBERS]:
            continue
        per = c.find(X + "period")
        s, e = per.findtext(X + "startDate"), per.findtext(X + "endDate")
        if s and e:
            ctx[c.get("id")] = (s, e)
    out = {}
    for el in root:
        tag = el.tag.split("}")[-1]
        if tag not in CONCEPTS or el.get("contextRef") not in ctx:
            continue
        s, e = ctx[el.get("contextRef")]
        try:
            val = int(el.text)
        except (TypeError, ValueError):
            continue
        row = out.setdefault(e, {"start": s, "end": e,
                                 "days": days_between(s, e)})
        row[CONCEPTS[tag]] = val
    return out


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
    seg_seen = []
    print("  %s (%s)" % (label, company))
    f = latest_filing(cik)
    g = azure_growth(f["primary"]) if f else None
    # The enclosing segment, with its period kept. Microsoft's latest filing
    # is usually a 10-K, so this is ANNUAL while AWS and Google Cloud are
    # quarterly -- the period travels with the number so the page cannot put
    # them in a row as though they were comparable.
    enclosing = None
    if f:
        seg_seen = seen = segment_members(f["instance"])
        for member, pretty in MSFT_SEGMENT_CANDIDATES:
            facts = segment_facts_any(f["instance"], member)
            if facts:
                end = sorted(facts)[-1]
                enclosing = facts[end]
                enclosing["segment"] = pretty
                enclosing["member"] = member
                break
        if enclosing is None:
            print("     WARNING: none of the known Microsoft segment "
                  "members is in this filing. Seen: %s" % ", ".join(seen))
    out["clouds"][label] = {
        "company": company, "cik": cik, "disclosed": False,
        "form": f["form"] if f else None,
        "filed": f["filed"] if f else None,
        "accession": f["accession"] if f else None,
        "growth": g,
        "enclosing_segment": enclosing,
        "segments_seen": seg_seen,
        "why": ("Azure is not a reportable segment, so no figure is "
                "required. US segment reporting obliges a company to "
                "publish revenue and operating income for the segments its "
                "management actually runs the business by, and Microsoft "
                "runs it by larger groupings -- Azure is a product line "
                "inside one of them, reported in commentary as a growth "
                "rate against a base it does not give. AWS and Google "
                "Cloud are each a reportable segment in their own right, "
                "which is the only reason their figures exist."),
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
