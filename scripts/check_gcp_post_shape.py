#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every GCP lab post carries the same anchors, headings and services columns.

    python scripts/check_gcp_post_shape.py
    python scripts/check_gcp_post_shape.py --self-test

Why this exists (2026-11-06)
----------------------------
Jay asked for one pattern across AWS, Azure and GCP: same headers, same
index, same columns. Checking found the GCP series was not even consistent
with ITSELF across twelve posts:

    anchors     eleven posts used  build / security / takeaways
                one used           implementation / security-cost / cleanup

    services    week 01, 02, 11    Service or tool | Purpose in this lab
    columns     weeks 03-09        Service         | Purpose in this lab
                week 10            Service | Purpose here | What it is
                week 12            Service | Why this lab needs it

    headings    week 10 said "Troubleshooting", not "Troubleshooting and
                Lessons"

AWS is the reference, for three reasons rather than seniority: it is the
only series internally consistent, its anchors name the section rather
than abbreviate it, and its THIRD column is what makes the section explain
instead of list -- which is what the standard asks of it, and exactly what
a two-column table drops silently.

check_lab_post_shape.py deliberately ALIASES anchor names so each series
can differ. That is why it never caught any of this: it was built to
tolerate the thing being checked here. This file is narrow on purpose --
GCP lab posts only, no browser, pure text -- so it stays fast enough to
sit in the pre-push hook without costing a push.

Scoped to the GCP series because that is the series being standardised.
Extending it to Azure, which diverges further (bare <h2> instead of
section wrappers, #prereqs / #seccost, its own References section), is a
separate decision about somebody else's posts.
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(ROOT, "posts")
SERIES_LABEL = "- GCP Weekly Lab"

ANCHORS = ["overview", "services", "architecture", "prerequisites",
           "implementation", "validation", "security-cost",
           "troubleshooting", "cleanup"]

HEADINGS = {
    "overview": "Lab Overview",
    "services": "Cloud Services and Concepts",
    "architecture": "Architecture and Workflow",
    "prerequisites": "Prerequisites",
    "implementation": "Implementation",
    "validation": "Validation and Evidence",
    "security-cost": "Security and Cost",
    "troubleshooting": "Troubleshooting and Lessons",
    "cleanup": "Cleanup and Key Takeaways",
}

COLUMNS = ["Service", "Purpose here", "What it is"]

# Start AFTER the services heading, not at it. The first version stopped the
# capture at the next `<h2 id="`, which - now that every heading carries an id -
# matched the services section's OWN heading on the very next line and captured
# nothing. Every post then reported "columns are []", a confident failure
# describing a table the check had not looked at.
SERVICES_SECTION = re.compile(
    r'id="services">\s*(?:<h2[^>]*>.*?</h2>)?(.*?)'
    r'(?=<div class="section"|<h2 id="(?!services))', re.S)
TH = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
TAGS = re.compile(r"<[^>]+>")


def strip(html):
    return TAGS.sub("", html).replace("&nbsp;", " ").strip()


def inspect(text):
    """Return a list of problems with one post's shape. Empty means fine."""
    problems = []

    found = re.findall(r'href="#([a-z0-9-]+)"', text)[:len(ANCHORS)]
    if found != ANCHORS:
        problems.append(
            "table of contents anchors are %s, expected %s"
            % (" ".join(found) or "(none)", " ".join(ANCHORS)))

    for anchor, title in HEADINGS.items():
        # The id belongs on the <h2> as well as the wrapper: the AWS series
        # puts it on both, and a deep link to #security-cost that lands on a
        # div the heading does not carry scrolls to the wrong place.
        if not re.search(r'<h2 id="%s">\s*%s\s*</h2>' % (re.escape(anchor),
                                                         re.escape(title)), text):
            problems.append('no <h2 id="%s"> reading "%s"' % (anchor, title))

    m = SERVICES_SECTION.search(text)
    if not m:
        problems.append("no services section to check columns in")
    else:
        cols = [strip(c) for c in TH.findall(m.group(1))[:3]]
        if cols != COLUMNS:
            problems.append(
                "services columns are %r, expected %r" % (cols, COLUMNS))
        else:
            # A three-column header over two-column rows renders as a table
            # with a blank final cell on every line, which looks like missing
            # content rather than broken markup.
            rows = re.findall(r"<tr>(?!\s*<th)(.*?)</tr>", m.group(1), re.S)
            ragged = [r for r in rows
                      if "<th" not in r and len(re.findall(r"<td", r)) != 3]
            if ragged:
                problems.append(
                    "%d services row(s) do not have 3 cells" % len(ragged))
    return problems


def gcp_posts():
    for fn in sorted(os.listdir(POSTS)):
        if not fn.endswith(".html"):
            continue
        path = os.path.join(POSTS, fn)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        if SERIES_LABEL in text:
            yield fn, text


def self_test():
    """Prove the check fails on each defect it was written for."""
    # Shaped like a REAL post: a table of contents, then one
    # <div class="section" id="..."> per section with its <h2 id="..."> nested
    # inside it. The first version of this fixture listed every heading up
    # front and then a bare `id="services">`, so the services regex matched
    # inside the HEADING rather than the section wrapper and captured nothing.
    # The check was correct and the fixture was not - which is the more
    # dangerous way round, because a self-test that fails on good input gets
    # "fixed" by loosening the check.
    table = ('<div class="table-scroll"><table><thead><tr>'
             + "".join("<th>%s</th>" % c for c in COLUMNS)
             + "</tr></thead><tbody>"
               "<tr><td>a</td><td>b</td><td>c</td></tr>"
               "</tbody></table></div>")
    sections = "".join(
        '<div class="section" id="%s">\n<h2 id="%s">%s</h2>%s</div>'
        % (a, a, HEADINGS[a], table if a == "services" else "<p>x</p>")
        for a in ANCHORS)
    good = ("".join('<li><a href="#%s">x</a></li>' % a for a in ANCHORS)
            + sections)
    cases = [
        ("a correct post", good, 0),
        ("old anchors", good.replace("#security-cost", "#security"), 1),
        ("two-column services table",
         good.replace("<th>What it is</th>", ""), 1),
        ("ragged row",
         good.replace("<td>a</td><td>b</td><td>c</td>", "<td>a</td><td>b</td>"), 1),
        ("heading without an id",
         good.replace('<h2 id="cleanup">', "<h2>"), 1),
    ]
    bad = 0
    for name, html, expect_at_least in cases:
        got = len(inspect(html))
        ok = (got == 0) if expect_at_least == 0 else (got >= expect_at_least)
        print("  %-28s problems=%d  %s" % (name, got, "ok" if ok else "SELF-TEST FAILED"))
        bad += 0 if ok else 1
    print("\nself-test:", "pass" if not bad else "FAIL")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    checked = failed = 0
    for fn, text in gcp_posts():
        checked += 1
        problems = inspect(text)
        if problems:
            failed += 1
            print("  [FAIL] %s" % fn)
            for p in problems:
                print("           %s" % p)
        else:
            print("  [ ok ] %s" % fn)

    print()
    if failed:
        print("%d of %d GCP lab post(s) do not match the shared shape." % (failed, checked))
        print("AWS is the reference: anchors %s," % " ".join(ANCHORS))
        print("and a services table of %s." % " | ".join(COLUMNS))
        return 1
    print("%d GCP lab post(s) checked; all match the shared AWS/Azure/GCP shape." % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
