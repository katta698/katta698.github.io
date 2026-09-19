#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Catch the sourcing gap that verify_claims cannot see.

Why this exists
---------------
verify_claims checks that the figures in a claim appear on the page the claim
cites. That is a real property and it has caught genuine errors. It has one
structural blind spot: **it only ever checks the source I chose.** If I cite the
wrong page, it passes. If the service was withdrawn last May, it passes. It
cannot ask "is there a page you should have read and did not".

That blind spot produced a live error in Architecture #48, published
2026-09-10. The post priced AWS CloudTrail Lake in detail, citing
aws.amazon.com/cloudtrail/pricing/ -- which carries the rates and says nothing
about availability. The service had been closed to new customers since
31 May 2026, and the notice sits at the top of
docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-lake.html, a page
the post never cited. Every check passed. A reader caught it.

The pattern behind it is simple enough to test for: **a pricing page tells you
what something costs, never whether you may still buy it.** Any post that
prices a service without also reading that service's documentation has taken
its facts from the one page that structurally cannot carry a deprecation.

What this checks
----------------
1. (offline, default) For every `aws.amazon.com/<service>/pricing/` URL cited
   in a post, require a docs.aws.amazon.com citation *for that same service*.

   The first version of this rule only asked for some docs page, on the theory
   that matching product slugs to doc-guide slugs was a rabbit hole not worth
   entering. Tested against #48 as published, it did not fire: the post cited
   docs for CloudWatch and VPC, just not for the service it had priced. A rule
   that passes the case it was written for is worse than no rule, so the slug
   match went in after all. It is cheap -- strip the non-alphanumerics from
   both sides and ask whether the pricing slug appears in any cited docs URL,
   which lines `cloudtrail` up with `docs.aws.amazon.com/awscloudtrail/...`
   and `network-firewall` with `docs.aws.amazon.com/network-firewall/...`.

2. (--online) Fetch every cited page and look for withdrawal language: closed
   to new customers, no longer available, end of support, deprecated. This is
   the check that would have caught #48 directly rather than by proxy, and it
   is slow, so it is opt-in and belongs in a weekly sweep rather than a
   per-post gate.

Exit status is 0 for findings by default: this is advisory, like
check_assertions. A sourcing gap is a prompt to go and look, not proof of an
error -- plenty of posts legitimately cite a pricing page for a service whose
documentation adds nothing.

Usage
-----
    python scripts/check_sources.py                  # all posts, offline
    python scripts/check_sources.py --series arch    # one series
    python scripts/check_sources.py --online         # also fetch and scan
"""

import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PRICING = re.compile(r'https?://aws\.amazon\.com/([a-z0-9][a-z0-9-]*)/pricing/?', re.I)
DOCS = re.compile(r'https?://docs\.aws\.amazon\.com/', re.I)
ANY_URL = re.compile(r'https?://[^\s"\'<>)]+')

# Services whose documentation does not live at a path containing their own
# name. Transit Gateway is the case that exposed this: its guide sits under
# /vpc/latest/tgw/, so the slug match alone reported arch-001 as unsourced when
# the post cites the Transit Gateway design guide in its reference list. A
# checker that cries wolf on a correctly sourced post gets switched off, so
# each of these is a real path checked by hand rather than a guess.
ALIASES = {
    "transit-gateway":  ["vpclatesttgw"],
    "vpc":              ["vpclatest"],
    "cloudtrail":       ["awscloudtrail"],
    "s3":               ["amazons3"],
    "cloudwatch":       ["amazoncloudwatch"],
    "ec2":              ["awsec2", "amazonec2"],
    "secrets-manager":  ["secretsmanager"],
    "systems-manager":  ["systemsmanager"],
    "eventbridge":      ["eventbridge"],
    "aws-cost-management": ["costmanagement", "awsaccountbilling"],
}

# --- the same blind spot, in the other two clouds --------------------------
#
# The AWS rule above is one instance of a general shape: *a post that asserts
# about a sub-topic while citing only the page above it in the hierarchy has
# taken its facts from a page that structurally cannot carry the qualifier.*
# AWS's instance is pricing-vs-docs. Azure's is licensing-vs-the-page-that-
# scopes-it, and it produced a live error in Azure Architecture #31, published
# 2026-09-12.
#
# That post asserted an access review spanning employees and guests "is billed
# two ways at once". It cited entra/fundamentals/licensing and
# id-governance/licensing-fundamentals -- both real, both correctly quoted,
# neither carrying the rule that decides the question. The page that does,
# id-governance/microsoft-entra-id-governance-licensing-for-guest-users, says
# guests are billed only for capabilities exclusive to ID Governance and that
# P2 capabilities are not billed to that meter. It is linked from both pages
# the post cited. Every check passed.
#
# Until this block existed, `--series az` and `--series gcp` inspected every
# post, had no rule to apply, and printed "0 with a sourcing gap" -- a green
# light that meant "nothing was tested". That is the failure this file's own
# docstring warns about, reproduced one cloud over.
#
# Each entry: (topic seen in prose, page that must be cited, context that makes
# the rule apply at all, message).
PLAN_TYPE = re.compile(
    r'\b(compute|ec2 instance|database|sagemaker(?: ai)?)\s+savings\s+plan',
    re.I)


def _plan_types(prose):
    """The distinct Savings Plans types a post names."""
    return {m.group(1).lower().replace(" ai", "") for m in PLAN_TYPE.finditer(prose)}


TOPIC_RULES = {
    "arch": [
        # arch-050, found by an external reviewer on 2026-09-13 and not by
        # anything here. The post reasons in detail about how commitments are
        # applied -- Reserved Instances before Savings Plans, EC2 Instance
        # before Compute -- citing sp-applying.html, and never cites the page
        # that says which plan types exist. AWS offers four: Compute, Database,
        # EC2 Instance and SageMaker AI. A reader can take a compute-specific
        # hierarchy for a universal one, and nothing in the post stops them.
        #
        # This is Mode A exactly: the page adjacent to the topic was read, the
        # page that governs it was not. It fires only on posts already citing
        # the Savings Plans user guide, and only when the prose names two or
        # more plan types -- one mention is a passing reference, two is a
        # comparison between types and that is when the set matters.
        (lambda prose: len(_plan_types(prose)) >= 2,
         re.compile(r'savingsplans/latest/userguide/plan-types', re.I),
         re.compile(r'savingsplans/latest/userguide', re.I),
         "compares Savings Plans types while citing the Savings Plans user "
         "guide but not plan-types -- AWS offers four (Compute, Database, EC2 "
         "Instance, SageMaker AI) and a compute-only hierarchy reads as "
         "universal without the page that enumerates them"),
    ],
    "az": [
        (re.compile(r'\bguests?\b|\bB2B\b', re.I),
         re.compile(r'licensing-for-guest-users', re.I),
         re.compile(r'entra/fundamentals/licensing|licensing-fundamentals', re.I),
         "discusses guest users while citing Entra licensing but cites no "
         "guest-users licensing page -- the general licensing pages carry the "
         "billing model, never the exclusions that scope it"),
    ],
    "gcp": [
        (re.compile(r'\bfree tier\b|\balways free\b', re.I),
         re.compile(r'/free\b|/pricing', re.I),
         re.compile(r'cloud\.google\.com', re.I),
         "discusses the free tier but cites no pricing or free-tier page -- a "
         "product page carries capability, never the allowance that limits it"),
    ],
    "daily": [
        # This series had no rule at all until now, across 36 posts publishing
        # daily -- the largest uncovered surface on the site, and the same
        # shape of hole that let Azure #31 out: a clean result meaning nothing
        # was tested.
        #
        # Its Mode A is specific and measurable. A Daily post is written from
        # an AWS announcement, and an announcement says what shipped. It does
        # not carry the quotas, the regional limits, the IAM requirements, or
        # the fact that the service was later closed to new customers. Those
        # live on the docs page, and a post that cites only the announcement
        # has read the press release and not the manual.
        #
        # What this rule does NOT catch, stated plainly because the standard
        # here is that a rule passing the case it was written for is worse than
        # no rule. daily-020 inferred a whole pricing model from the What's New
        # page saying nothing about pricing -- and it cites both an
        # announcement and docs, so this rule passes it.
        #
        # A second rule was written for that shape and rejected on measurement.
        # "asserts a price while citing no pricing page" fires on 31 of 36
        # daily posts at the loose end and still 31 across the corpus when
        # tightened to definite assertions only, because "no additional charge"
        # is a phrase AWS puts in the announcement itself -- so the
        # announcement IS the governing source for it, and the rule would be
        # wrong in premise as well as loud. Inference from an absence is not
        # detectable by asking which pages were cited. That one needs a reader,
        # like the prose-against-claim drift recorded in VALIDATION.md.
        #
        # The trigger is the citation pattern rather than the prose, so the
        # topic slot is unconditional: any post whose sources include an
        # announcement is asked whether it also read documentation. That is
        # why it is a callable returning True rather than a word list -- there
        # is no phrase that reliably marks "this sentence needs the manual",
        # and guessing one would both miss and cry wolf.
        #
        # Measured across the corpus: 2 of 36 daily posts, and nothing in any
        # other series. Security bulletins are deliberately not caught --
        # daily-026 cites four of them for a CVE, and for a CVE the bulletin
        # IS the governing page.
        (lambda prose: True,
         re.compile(r'docs\.aws\.amazon\.com', re.I),
         re.compile(r'aws\.amazon\.com/about-aws/whats-new', re.I),
         "is written from an AWS announcement and cites no docs.aws.amazon.com "
         "page -- a What's New entry carries what shipped, never the quotas, "
         "the regional limits or the withdrawal notice that scope it"),
    ],
}


# The prefixes that are actually series. Everything else in posts/ is a
# standalone piece, and splitting its filename on the first hyphen invents
# series called "ansible" and "why" -- which made the coverage note below
# unreadable, and an unreadable warning is an ignored one.
#
# "daily" was missing from this tuple, so series_of() returned '' for all 36
# AWS Daily Intelligence posts. No topic rule could ever fire on them, and the
# coverage note below -- which exists precisely to name the series nothing is
# checking -- could not name this one either, because it lists what series_of()
# found. The largest uncovered series on the site was invisible to the warning
# written to report uncovered series.
#
# Found while adding the first daily rule: the rule measured zero findings on
# posts it should have flagged. A rule that cannot be reached looks exactly
# like a corpus with nothing wrong in it.
SERIES_PREFIXES = ("gcpweekly", "arch", "azw", "az", "gcp", "weekly", "week",
                   "daily")


def series_of(path):
    """arch-042 -> arch, az-031 -> az, gcpweekly-005 -> gcpweekly.

    Longest prefix first, so gcpweekly-005 is not read as gcp and azw-005 is
    not read as az.
    """
    name = os.path.basename(path)
    for p in SERIES_PREFIXES:
        if name.startswith(p + "-"):
            return p
    return ""


def check_topics(path):
    """Return findings for the topic rules of this post's series."""
    rules = TOPIC_RULES.get(series_of(path))
    if not rules:
        return []
    text = io.open(path, encoding="utf-8").read()
    urls = " ".join(urls_in(text))
    # The pages the post's CLAIMS cite, as distinct from every URL in the file.
    # A link in a reference list is not evidence that the page was read -- that
    # is the exact wording of what went wrong in GCP #30, where "the workflow
    # that produced the error read excerpts, and the reference list carried the
    # unread page as a link". A source: on a claim is evidence; a link is not.
    claim_urls = " ".join(re.findall(r'^\s*source:\s*(\S+)', text, re.M))
    prose = re.sub(r'<[^>]+>', ' ', text)
    out = []
    for topic, required, context, message in rules:
        if not context.search(claim_urls):
            continue
        # `topic` is normally a compiled pattern, but a rule whose trigger is
        # "more than one of these appears" cannot be written as one search.
        # Allowing a callable keeps that logic beside the rule it belongs to
        # rather than spreading a special case through this loop.
        hit = topic(prose) if callable(topic) else bool(topic.search(prose))
        if not hit:
            continue
        if required.search(claim_urls):
            continue
        out.append(message)
    return out


# Phrases AWS uses when a service stops being an option. Kept deliberately
# short: every one of these has appeared verbatim on a service page, and a
# longer list of near-synonyms would fire on ordinary prose about deprecating
# a customer's own resources.
WITHDRAWN = [
    "no longer be open to new customers",
    "no longer open to new customers",
    "not open to new customers",
    "no longer available to new customers",
    "will no longer be available",
    "end of support",
    "will be discontinued",
    "availability change",
]


def posts_for(series):
    pattern = "posts/%s-*.html" % series if series else "posts/*.html"
    return sorted(glob.glob(os.path.join(ROOT, pattern)))


def urls_in(text):
    return ANY_URL.findall(text)


def norm(s):
    """Lower-case and drop everything that is not a letter or digit.

    AWS spells the same service differently in its two URL spaces --
    aws.amazon.com/cloudtrail/pricing/ against
    docs.aws.amazon.com/awscloudtrail/, aws.amazon.com/network-firewall/
    against docs.aws.amazon.com/network-firewall/. Normalising both sides and
    testing for containment handles the aws- prefix and the hyphens without
    needing a lookup table to maintain.
    """
    return re.sub(r'[^a-z0-9]', '', s.lower())


def check_offline(path):
    """Return a list of finding strings for one post."""
    text = io.open(path, encoding="utf-8").read()
    urls = urls_in(text)
    priced = sorted({m.group(1).lower() for u in urls for m in [PRICING.search(u)] if m})
    if not priced:
        return []
    docs = norm(" ".join(u for u in urls if DOCS.search(u)))

    def sourced(svc):
        if norm(svc) in docs:
            return True
        return any(alias in docs for alias in ALIASES.get(svc, []))

    missing = [svc for svc in priced if not sourced(svc)]
    if not missing:
        return []
    return ["prices %s but cites no docs.aws.amazon.com page for %s -- a "
            "pricing page carries rates, never availability"
            % (", ".join(missing), "it" if len(missing) == 1 else "them")]


def check_online(path):
    """Fetch every cited page and look for withdrawal language."""
    try:
        from urllib.request import Request, urlopen
    except ImportError:                                        # pragma: no cover
        return ["--online needs Python 3"]
    text = io.open(path, encoding="utf-8").read()
    seen, found = set(), []
    for url in urls_in(text):
        url = url.rstrip('.,;")')
        if url in seen or not re.search(r'(aws|amazon)\.com', url):
            continue
        seen.add(url)
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 check_sources"})
            body = urlopen(req, timeout=25).read().decode("utf-8", "replace")
        except Exception:                                      # noqa: BLE001
            continue
        low = body.lower()
        for phrase in WITHDRAWN:
            if phrase in low:
                found.append('%s says "%s"' % (url, phrase))
                break
    return found


# Controls, for the same reason check_assertions.py has them: a topic rule
# edited into inertness reports a clean corpus, and a clean corpus is exactly
# what this file was written to stop being trusted blindly. This file had none
# until the arch rule was added.
def selftest():
    bad = []
    # Each rule must fire on prose that should trip it and stay quiet on prose
    # that should not.
    two = "Compute Savings Plans apply after EC2 Instance Savings Plans."
    one = "A Compute Savings Plan covers Fargate and Lambda usage."
    if len(_plan_types(two)) < 2:
        bad.append("_plan_types no longer sees two distinct types")
    if len(_plan_types(one)) != 1:
        bad.append("_plan_types miscounts a single mention")
    if _plan_types("savings plans are applied by percentage"):
        bad.append("_plan_types matches prose naming no type at all")
    # The callable path in check_topics must actually be exercised.
    if not callable(TOPIC_RULES["arch"][0][0]):
        bad.append("the arch plan-types rule is no longer a callable")
    for key in ("az", "gcp", "daily"):
        if not TOPIC_RULES.get(key):
            bad.append("topic rules for %s have gone missing" % key)

    # series_of() has to reach every series that owns a rule. "daily" was
    # absent from SERIES_PREFIXES, so its rule was unreachable and measured
    # zero findings on posts it should have flagged -- which looks exactly
    # like a clean corpus.
    for key in TOPIC_RULES:
        if key not in SERIES_PREFIXES:
            bad.append("%s has topic rules but series_of() cannot return it"
                       % key)
    if series_of("posts/daily-001-x.html") != "daily":
        bad.append("series_of no longer recognises the daily series")
    return bad


def main(argv):
    broken = selftest()
    if broken:
        print("check_sources.py is not checking anything:")
        for b in broken:
            print("   %s" % b)
        return 2

    online = "--online" in argv
    series = None
    if "--series" in argv:
        series = argv[argv.index("--series") + 1]

    total = flagged = 0
    seen_series = set()
    for path in posts_for(series):
        total += 1
        seen_series.add(series_of(path))
        findings = check_offline(path) + check_topics(path)
        if online:
            findings += check_online(path)
        if findings:
            flagged += 1
            print(os.path.basename(path))
            for f in findings:
                print("   %s" % f)

    print("\nChecked %d post(s): %d with a sourcing gap%s."
          % (total, flagged, "" if online else " (offline rules only)"))

    # Say what was *not* tested. Before this existed, `--series az` printed
    # "0 with a sourcing gap" while holding no Azure rule at all, and that
    # green light is what let Azure #31 through. A count of zero has to be
    # distinguishable from an absence of rules, or it means nothing.
    untested = sorted(s for s in seen_series
                      if s and s not in TOPIC_RULES and s != "arch")
    if untested:
        print("  note: no topic rules exist for %s -- posts in %s were "
              "checked against the AWS pricing rule only, which cannot fire "
              "on them. A clean result here is not evidence."
              % (", ".join(untested), "that series" if len(untested) == 1
                 else "those series"))
    if not online:
        print("Run with --online to fetch cited pages and scan for withdrawal "
              "notices -- slow, and the check that catches a closed service.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
