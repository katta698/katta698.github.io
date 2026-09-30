#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A lab post's sections must contain what their headings promise.

    python scripts/check_lab_post_shape.py                 # every lab-week post
    python scripts/check_lab_post_shape.py week-06         # one post
    python scripts/check_lab_post_shape.py --self-test     # prove it can fail

Why this exists
---------------
Two defects shipped in the GCP series, both found by Jay reading the rendered
page rather than by anything here.

1. "Architecture — How It Fits Together" with no diagram. Week 6 carried an
   ASCII schematic in a <pre> and nothing else. On a phone that reads as a
   command prompt sitting under an architecture heading. Weeks 1 to 5 all carry
   an inline SVG, so the post was the odd one out and nothing said so.

2. "What You Need to Know — Skills & Tools" with no skills and no tools. Weeks 1
   and 2 carry a service list, a tooling list and a concepts grid. Weeks 3
   through 6 quietly dropped all three and kept only prose, so the heading
   promised an inventory that four posts did not deliver.

Both are mechanically detectable and neither was detected. That is the whole
argument for this file: a section whose heading names a form should be checked
for that form, or the heading is decoration and a reader has to find out by
being disappointed.

What it checks, and what it deliberately does not
-------------------------------------------------
It checks for the PRESENCE of a shape, never its quality. A diagram that is
wrong, ugly or misleading passes here; only an absent one fails. Judging whether
a diagram explains the architecture is a reading task and this is not a reader.

It does not require a <pre> schematic to be removed. Week 5 carries both an SVG
and an ASCII block and is better for it -- the check wants the diagram to exist,
not the text to go away.

Scope is the GCP Weekly Lab, because that is the series whose convention was
established and then broken. The AWS and Azure labs predate it and use a
different section vocabulary; running there would flag posts against a standard
they were never written to, which is how a check learns to cry wolf.
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

# Every lab post from this week on must show the files it was built from.
# Asked for on 2026-09-30: prose describes what the Terraform does and never
# shows a reader what was actually written, so "these are the scripts" has to be
# visible. Earlier posts are left alone rather than retrofitted - the rule starts
# where it was agreed.
#
# A rendered card, named *terraform-layout*, matching the Azure and AWS labs so a
# reader moving between the three series meets the same object each week. Built
# by scripts/screenshots/render_tree_card.py in the lab repo from a tree.txt
# whose line counts come from wc -l.
#
# Two wrong turns are recorded so they are not retaken. A screenshot of the
# GitHub directory listing: rejected, because anyone can open the repo and a list
# of filenames says nothing about what is in them. An inline <pre> block: closer,
# but it inherits the post's code styling, reads as a code sample rather than a
# figure, and looked nothing like the other two clouds.
CODE_SHOT_FROM_WEEK = 7
CODE_SHOT_MARKER = "terraform-layout"
WEEK_RE = re.compile(r"week-(\d+)")

# section id -> (human name, regex that proves the promised shape is present)
REQUIRED = {
    "architecture": (
        "a diagram (inline <svg> or an <img>)",
        re.compile(r"<svg|<img", re.I),
    ),
    "skills": (
        "an inventory (a <ul> list of services/tooling)",
        re.compile(r"<ul\b", re.I),
    ),
}


def front_matter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def section(text, sid):
    """The markup of one section, from its opening div to the next section."""
    m = re.search(
        r'<div class="section" id="%s".*?(?=<div class="section"|\Z)' % re.escape(sid),
        text,
        re.S,
    )
    return m.group(0) if m else None


def check_text(text, name, report, week=None):
    problems = []
    if week is not None and week >= CODE_SHOT_FROM_WEEK and CODE_SHOT_MARKER not in text:
        problems.append(
            f"no Terraform layout card (expected an image named *{CODE_SHOT_MARKER}*, "
            "built with render_tree_card.py)"
        )
    for sid, (want, pattern) in REQUIRED.items():
        sec = section(text, sid)
        if sec is None:
            continue  # a post may legitimately omit a section; not this check's job
        if not pattern.search(sec):
            problems.append(f"#{sid} has no {want}")
    if problems:
        for p in problems:
            report.append(f"  [FAIL] {name}: {p}")
    else:
        report.append(f"  [ ok ] {name}")
    return len(problems)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*", help="substring of a post filename")
    ap.add_argument("--series", help="accepted and ignored; scope is fixed")
    ap.add_argument("--self-test", action="store_true",
                    help="prove the check fails on a post with the shape removed")
    args = ap.parse_args()

    if args.self_test:
        good = ('<div class="section" id="skills"><h2>x</h2><ul><li>a</li></ul></div>'
                '<div class="section" id="architecture"><h2>y</h2><svg></svg></div>')
        stripped = ('<div class="section" id="skills"><h2>x</h2><p>prose only</p></div>'
                    '<div class="section" id="architecture"><h2>y</h2><pre>ascii</pre></div>')
        good_w7 = good + f'<img src="05-{CODE_SHOT_MARKER}.png"/>'
        r1, r2, r3 = [], [], []
        ok = check_text(good_w7, "synthetic-good", r1, CODE_SHOT_FROM_WEEK)
        bad = check_text(stripped, "synthetic-stripped", r2)
        nocode = check_text(good, "synthetic-no-code-shot", r3, CODE_SHOT_FROM_WEEK)
        print("\n".join(r1 + r2 + r3))
        if ok == 0 and bad == 2 and nocode == 1:
            print("\nself-test passed: clean post passes, stripped post fails on both")
            print("sections, and a post missing the Terraform layout card fails too.")
            return 0
        print("\nSELF-TEST FAILED: the check cannot detect the defect it exists for.")
        return 1

    report, failures, checked = [], 0, 0
    for fn in sorted(os.listdir(POSTS)):
        if not fn.endswith(".html"):
            continue
        if args.posts and not any(a in fn for a in args.posts):
            continue
        path = os.path.join(POSTS, fn)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if SERIES_LABEL not in front_matter(text):
            continue
        checked += 1
        m = WEEK_RE.search(fn)
        failures += check_text(text, fn, report, int(m.group(1)) if m else None)

    print("\n".join(report))
    print(f"\n{checked} {SERIES_LABEL} post(s) checked.")
    if failures:
        print(f"{failures} section(s) do not contain what their heading promises.")
        print("Add the missing diagram or inventory, or change the heading.")
        return 1
    print("Every section contains the shape its heading promises.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
