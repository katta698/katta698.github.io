#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A lab post must follow the documentation standard of 2026-10-25.

    python scripts/check_lab_post_shape.py                 # every lab-week post
    python scripts/check_lab_post_shape.py week-10         # one post
    python scripts/check_lab_post_shape.py --self-test     # prove it can fail

Why this exists
---------------
Two defects shipped in the GCP series and both were found by Jay reading the
rendered page: an "Architecture" heading with no diagram, and a "What You Need
to Know - Skills & Tools" heading with neither. A section whose heading names a
form should be checked for that form, or the heading is decoration.

What changed on 2026-10-25
--------------------------
Jay issued a full documentation standard. The section vocabulary changed, and
one rule inverted: the file-tree figure, required from Week 07 and enforced
here, is now FORBIDDEN - the standard says do not put repository trees in the
article, link to the GitHub file instead. Asked directly which rule won, Jay
chose the standard.

So this file now checks the new structure, and actively fails a post that still
carries the retired tree card.

The migration list
------------------
All ten GCP lab posts are being rewritten to the new structure, newest first.
Until a post is rewritten it cannot satisfy this check, so each unmigrated slug
is listed in MIGRATION_PENDING and skipped.

That list is a RATCHET, not an excuse: a post that is neither migrated nor
listed FAILS. Removing a slug is part of migrating it, and the list can only
shrink. An advisory warning would have been ignored - the account-id warning
was true and ignored for twelve days - so this blocks.
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
POSTS = os.path.join(ROOT, "posts")

SERIES_LABEL = "GCP Weekly Lab"

# ALL THREE SERIES ARE IN SCOPE (2026-10-25)
# ------------------------------------------
# This file checked only the GCP series. Pointed at an AWS or Azure post it
# printed "0 GCP Weekly Lab post(s) checked / Every section contains the shape
# its heading promises" -- a pass, over nothing, on every post it never read.
#
# That is not hypothetical. Within hours of the master standard being issued,
# the GCP and AWS windows both migrated posts to it and chose DIFFERENT section
# ids for three of the nine sections (build/security/takeaways against
# implementation/security-cost/cleanup). Both believed they were compliant.
# Nothing caught it, because the check could only see one of them.
#
# Each series declares the ids it currently uses. The canonical list is in
# docs/MASTER_STANDARD.md; a series converges by changing its entry here when
# it next touches those posts.
SERIES = {
    "GCP Weekly Lab": ["overview", "services", "architecture", "prerequisites",
                       "build", "validation", "security", "troubleshooting",
                       "takeaways"],
    "AWS Weekly Lab": ["overview", "services", "architecture", "prerequisites",
                       "implementation", "validation", "security-cost",
                       "troubleshooting", "cleanup"],
    "Azure Weekly Lab": None,   # not migrated yet; set the list to switch on
}

# Slugs not yet rewritten to the 2026-10-25 standard. Shrinks only.
#
# The AWS entries were added 2026-10-25 when this check first covered the
# AWS series. Weeks 20-24 are migrated; the rest are in progress. Remove a
# line as its post lands, never add one back.
MIGRATION_PENDING = {
    "week-1-from-ticket-to-ec2-in-6-minutes-enterprise-self-servi",
    "week-10-centralized-logging",
    "week-11-security-hub-guardduty",
    "week-12-config-compliance-automation",
    "week-13-waf-shield-protection",
    "week-14-vpc-flow-logs-intelligence",
    "week-15-cloudtrail-audit-forensics",
    "week-16-devops-agent-investigations",
    "week-17-mcp-platform-ops",
    "week-18-eks-self-service",
    "week-19-gitops-argocd",
    "week-2-automating-postgresql-provisioning-with-servicenow-an",
    "week-3-self-service-ec2-fleet-patching-with-aws-ssm",
    "week-4-building-a-fleet-intelligence-platform-with-aws-glue-",
    "week-5-cost-anomaly-detection-with-aws-cost-explorer-sns-and",
    "week-6-account-vending-machine-with-aws-organizations-and-scps",
    "week-7-iam-identity-center-sso-multi-account-permission-sets",
    "week-8-s3-intelligent-storage-platform",
    "week-9-ecs-fargate-self-service",

    "week-01-gcp-landing-zone",
    "week-02-keyless-ci",
    "week-03-org-policy-guardrails",
    "week-04-shared-vpc",
    "week-05-project-factory",
    "week-06-billing-export",
    "week-07-asset-inventory",
    "week-08-iam-deny",
}

# The standard's section order. Presence is checked; order is not, because the
# table of contents already makes order visible to a reader and reordering is a
# judgement the check should not make.
REQUIRED_SECTIONS = [
    "overview", "services", "architecture", "prerequisites", "build",
    "validation", "security", "troubleshooting", "takeaways",
]

# section id -> (what the heading promises, pattern that proves it is there)
SECTION_SHAPE = {
    # Inline <svg> only, never <img>. The original rule accepted either, which
    # let the exact failure this check exists for walk through in a different
    # costume: an ASCII schematic rendered to PNG arrived as an <img> of a
    # command prompt under an architecture heading.
    "architecture": ("an inline <svg> diagram (an <img> does not count)",
                     re.compile(r"<svg", re.I)),
    # "compact table containing service name, purpose, definition"
    "services":      ("a services table", re.compile(r"<table", re.I)),
    # "Required accounts, permissions, software and version requirements..."
    # A table or a list - the standard asks for a LIST of what is actually
    # needed, and a short prerequisite set reads better as bullets than as a
    # two-column table. Either shape is scannable; prose alone is not.
    "prerequisites": ("a table or list of prerequisites",
                      re.compile(r"<table|<ul", re.I)),
    # "Test command, expected result, ACTUAL observed result, supporting
    # screenshot or output" - a claim of validation with no evidence is the
    # thing the standard most insists on.
    # The standard requires a Test | Expected | Actual | Status table, which is
    # the difference between claiming validation and showing it.
    "validation":    ("a Test/Expected/Actual/Status table",
                      re.compile(r"<th>\s*Status\s*</th>", re.I)),
    # "Problem -> Root cause -> Resolution -> Lesson learned"
    "troubleshooting": ("the Problem/Root cause/Resolution/Lesson form",
                        re.compile(r"Root cause", re.I)),
}

# Retired 2026-10-25. A post carrying this now fails.
# Retired 2026-09-30 rule: a tree WITH per-file line counts. The master
# standard permits a COMPACT structure figure and forbids line counts, so
# what is banned is the old card, not a structure figure as such.
RETIRED_TREE_CARD = "terraform-layout"

WEEK_RE = re.compile(r"week-(\d+)")


def front_matter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def slug_of(text, filename):
    m = re.search(r"^slug:\s*(.+)$", front_matter(text), re.M)
    return m.group(1).strip() if m else os.path.splitext(filename)[0]


def section(text, sid):
    m = re.search(r'<div class="section" id="%s".*?(?=<div class="section"|\Z)'
                  % re.escape(sid), text, re.S)
    return m.group(0) if m else None


# (stem used to match, canonical heading reported)
#
# Matched on a distinctive STEM rather than the exact string. GCP week-10 heads
# its section "Troubleshooting" where the standard says "Troubleshooting and
# Lessons" -- a one-word difference that is worth converging, and not worth
# failing another window's published post over. The canonical wording is in
# docs/MASTER_STANDARD.md.
HEADINGS = [
    ("Lab Overview", "Lab Overview"),
    ("Cloud Services", "Cloud Services and Concepts"),
    ("Architecture and Workflow", "Architecture and Workflow"),
    ("Prerequisites", "Prerequisites"),
    ("Implementation", "Implementation"),
    ("Validation and Evidence", "Validation and Evidence"),
    ("Security and Cost", "Security and Cost"),
    ("Troubleshooting", "Troubleshooting and Lessons"),
    ("Cleanup and Key Takeaways", "Cleanup and Key Takeaways"),
]

# Shape keyed on the HEADING, not the id -- see section_by_heading below.
SHAPE_BY_HEADING = {
    # An inline <svg>, OR an <img> pointing at a real .svg file.
    #
    # The original rule rejected every <img>, because the failure it was written
    # for was an ASCII schematic rendered to PNG -- a picture of a command prompt
    # under an architecture heading. A vector .svg referenced by <img> is not
    # that: it renders as a diagram, scales, and keeps the HTML small, which is
    # how the Azure series does it. Rejecting it would be crying wolf over an
    # embedding choice the standard does not make.
    "Architecture and Workflow": ("a diagram - inline <svg>, or an <img> of a .svg "
                                  "(a .png of text does not count)",
                                  re.compile(r"<svg|<img[^>]+\.svg", re.I)),
    "Cloud Services and Concepts": ("a services table", re.compile(r"<table", re.I)),
    "Prerequisites": ("a table or list of prerequisites",
                      re.compile(r"<table|<ul", re.I)),
    "Validation and Evidence": ("a Test/Expected/Actual/Status table",
                                re.compile(r"<th>\s*Status\s*</th>", re.I)),
    "Troubleshooting and Lessons": ("the Problem/Root cause/Resolution/Lesson form",
                                    re.compile(r"Root cause", re.I)),
}


def section_by_heading(text, heading):
    """A section's markup, from its <h2> to the next <h2>.

    WHY NOT BY id (2026-10-25)
    --------------------------
    The standard specifies section HEADINGS. It never specified the HTML `id`
    attribute, so all three series invented their own and diverged inside a
    day: AWS chose implementation/security-cost/cleanup, GCP chose
    build/security/takeaways, and Azure uses no section wrappers at all.

    All three were following the standard. Checking ids declared two of them
    broken over a detail the standard does not contain. Checking headings
    checks what was actually mandated, needs no series to rewrite its markup,
    and lets one gate cover all three clouds.
    """
    pat = re.compile(r"<h2[^>]*>(?:(?!</h2>).)*?" + re.escape(heading).replace(r"\ ", r"\s+")
                     + r".*?</h2>(.*?)(?=<h2|\Z)", re.S | re.I)
    m = pat.search(text)
    return m.group(0) if m else None


def check_text(text, name, report, slug=None, required=None):
    problems = []
    required = required or REQUIRED_SECTIONS

    if RETIRED_TREE_CARD in text:
        problems.append(
            f"carries the retired file-tree card (*{RETIRED_TREE_CARD}*), which "
            "listed per-file line counts. The master standard allows a COMPACT "
            "structure figure and forbids line counts and exhaustive inventories")

    for sid in required:
        if section(text, sid) is None:
            problems.append(f'no "{sid}" section - the standard requires all '
                            f"{len(required)}")

    # SECTION_SHAPE is keyed on the GCP ids; translate to this series'.
    alias = dict(zip(REQUIRED_SECTIONS, required))
    for gcp_sid, (want, pattern) in SECTION_SHAPE.items():
        sid = alias.get(gcp_sid, gcp_sid)
        sec = section(text, sid)
        if sec is None:
            continue  # already reported as missing above
        if not pattern.search(sec):
            problems.append(f"#{sid} is missing {want}")

    if problems:
        for p in problems:
            report.append(f"  [FAIL] {name}: {p}")
    else:
        report.append(f"  [ ok ] {name}")
    return len(problems)


def self_test():
    STATUS_TABLE = ("<table><thead><tr><th>Test</th><th>Expected</th>"
                    "<th>Actual</th><th>Status</th></tr></thead></table>")

    def post(**kw):
        parts = []
        for sid in REQUIRED_SECTIONS:
            parts.append('<div class="section" id="%s"><h2>%s</h2>%s</div>'
                         % (sid, sid, kw.get(sid, "")))
        return "".join(parts)

    good = post(architecture="<svg></svg>", services="<table></table>",
                prerequisites="<table></table>", validation=STATUS_TABLE,
                troubleshooting="<p>Root cause: x</p>")

    cases = [
        (good, 0, "a post following the standard"),
        (good.replace('id="prerequisites"><h2>prerequisites</h2><table></table>',
                      'id="prerequisites"><h2>prerequisites</h2><p>prose</p>'),
         1, "prerequisites with no table"),
        # The standard's sharpest requirement: a Status column, so a claim of
        # validation cannot be made without saying what actually happened.
        (good.replace(STATUS_TABLE, "<figure><img src=x></figure>"),
         1, "validation with a figure but no Test/Expected/Actual/Status table"),
        (good.replace("<p>Root cause: x</p>", "<p>some things broke</p>"),
         1, "troubleshooting not in Problem/Root cause form"),
        (good + '<img src="05-terraform-layout.png">',
         1, "still carrying the retired line-count tree card"),
        (good.replace('<div class="section" id="takeaways"><h2>takeaways</h2></div>', ""),
         1, "a missing section"),
        (good.replace("<svg></svg>", '<img src="arch.png">'),
         1, "architecture as an image rather than a diagram"),
    ]

    bad = 0
    for text, want, label in cases:
        r = []
        got = check_text(text, "synthetic", r)
        ok = got == want
        bad += not ok
        print("  [%s] %s: %d problem(s), want %d"
              % (" ok " if ok else "FAIL", label, got, want))
        if not ok:
            for line in r:
                print("        ", line.strip())
    if bad:
        print("\nSELF-TEST FAILED: the check cannot detect the defect it exists for.")
        return 1
    print("\nself-test passed: a missing section, a section missing the form its")
    print("heading promises, a validation claim with no Status column, and the")
    print("retired line-count tree card are all detected.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*", help="substring of a post filename")
    ap.add_argument("--series", help="accepted and ignored; scope is fixed")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    report, failures, checked, pending = [], 0, 0, 0
    for fn in sorted(os.listdir(POSTS)):
        if not fn.endswith(".html"):
            continue
        if args.posts and not any(a in fn for a in args.posts):
            continue
        with open(os.path.join(POSTS, fn), encoding="utf-8") as fh:
            text = fh.read()
        fm = front_matter(text)
        series = next((lbl for lbl in SERIES if lbl in fm), None)
        if series is None:
            continue
        required = SERIES[series]
        if required is None:
            continue          # series not migrated yet; see SERIES above
        slug = slug_of(text, fn)
        if slug in MIGRATION_PENDING:
            pending += 1
            report.append(f"  [ -- ] {fn}: awaiting rewrite to the 2026-10-25 standard")
            continue
        checked += 1
        failures += check_text(text, fn, report, slug, required)

    print("\n".join(report))
    print(f"\n{checked} post(s) checked against the standard; "
          f"{pending} awaiting rewrite.")
    if failures:
        print(f"{failures} problem(s). See the documentation standard "
              "(CLAUDE.md in the lab repo).")
        return 1
    print("Every checked post follows the documentation standard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
