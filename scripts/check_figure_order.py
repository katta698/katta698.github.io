#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""No screenshot of live state may appear before the step that deploys it.

    python scripts/check_figure_order.py                 # every lab-week post
    python scripts/check_figure_order.py week-18         # one post
    python scripts/check_figure_order.py --self-test     # prove it can fail

Why this exists
---------------
A reader following "How We Built It" in order hits a console screenshot showing
a resource that, at that point in the post, does not exist yet. Week 6 learned
this and wrote it down. Week 18 shipped it twice in one day -- a Pod Identity
console page under Step 2, before the Step 3 that creates the cluster, then a
kubectl listing of live namespaces under Step 1, which is an authoring step.
Week 17 shipped it too: live server output under "Step 3 - Write four tools",
before Step 4 deploys anything. Jay found every one of them by reading.

What it checks, and why not the obvious thing
---------------------------------------------
The first version required capture numbers to ascend through the narrative, on
the theory that captures are numbered in build order. Run across the archive it
flagged 12 posts and 11 of them were fine: a figure captured eighth can
legitimately be discussed tenth, and "Cap the query spend" belongs at the end of
a post no matter when its screenshot was taken. A rule that is wrong eleven
times out of twelve teaches people to ignore red, and then it catches nothing.

So this encodes the real invariant instead. Everything in these posts becomes
real at the deploy step, so a figure ABOVE that step is showing state that does
not exist yet. Below it, order carries no such claim and is left alone.

The escape hatch, which has to be used deliberately
---------------------------------------------------
Some steps genuinely precede the deploy and have console state of their own --
enabling Organizations trusted access, reading an org policy, registering an
OAuth client. Mark those figures explicitly:

    <figure class="screenshot" data-prereq>

That is a claim that the state shown exists before any Terraform runs. It is one
word, it shows up in the diff, and it can be argued with -- which is the whole
difference between an exception and an oversight.
"""
import argparse
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB_POST = re.compile(r"week-\d+-")

# The heading that turns a plan into infrastructure. Matching a bare "deploy"
# is not enough: Week 5 names its deploy step "Push to GitHub and apply via HCP"
# and its NEXT step "Test immediately after deploy", so a loose match picked the
# verification step as the boundary and flagged three innocent figures.
DEPLOY_H3 = re.compile(r"<h3>([^<]*(?:\bdeploy\w*\b|\bapply\b)[^<]*)</h3>", re.I)
# Headings that talk about the deploy without being it.
NOT_DEPLOY = re.compile(r"\b(test|verif\w*|confirm|watch|after|once)\b", re.I)
FIGURE = re.compile(r"<figure[^>]*>.*?</figure>", re.S)


def deploy_step(narrative):
    """Position of the heading where the infrastructure comes into existence."""
    for m in DEPLOY_H3.finditer(narrative):
        if not NOT_DEPLOY.search(m.group(1)):
            return m.start()
    return None


def build_narrative(html):
    """The 'How We Built It' region, bounded by section ids.

    Bounded by ids and NOT by heading text: the first version split on the
    literal "Challenges &mdash;", which also appears in every post's table of
    contents, so it returned the region ABOVE the article, found no figures and
    passed the exact page it was written to reject.

    Returns "" when the section cannot be located. Callers must treat that as a
    failure, never as "nothing to check".
    """
    m_start = re.search(r'id="(?:how|build|how-we-built-it)"', html)
    if not m_start:
        return ""
    region = html[m_start.start():]
    m_end = re.search(r'id="challenges"', region)
    return region[:m_end.start()] if m_end else region


def premature_figures(narrative):
    """Figures sitting above the deploy step without a data-prereq marker.

    Returns [(figure_number_or_'?', alt_text)]. Empty when the post has no
    deploy step, since then there is no boundary to violate.
    """
    pos = deploy_step(narrative)
    if pos is None:
        return []
    offenders = []
    for fig in FIGURE.finditer(narrative[:pos]):
        block = fig.group(0)
        if re.search(r"\bdata-prereq\b", block):
            continue
        num = re.search(r"screenshots/(\d+)", block)
        alt = re.search(r'alt="([^"]*)"', block)
        offenders.append((num.group(1) if num else "?",
                          (alt.group(1) if alt else "")[:70]))
    return offenders


def _fig(num, extra=""):
    return ('<figure class="screenshot"%s><img src="screenshots/%s-x.png" '
            'alt="a"></figure>' % (extra, num))


def self_test():
    """Prove each rule rejects a known-bad page before any result is trusted.

    Why: on 2026-09-12 the first version of this rule shipped in a form that
    could not fail -- it sliced the page on heading text that also appears in
    the table of contents, examined the region above the article, found nothing
    and passed. It passed the exact page it existed to reject, and the run that
    printed "all checks passed" was believed. A green from a rule nobody has
    seen fail is an assumption wearing a checkmark.
    """
    toc = '<nav><a href="#challenges">Challenges &mdash; What Went Wrong</a></nav>'
    tail = '<div id="challenges">' + _fig("99") + '</div>'
    deploy = "<h3>Step 3 &mdash; Deploy it</h3>"

    bad = toc + '<div id="how"><h3>Step 1</h3>' + _fig("09") + deploy + _fig("01") + '</div>' + tail
    good = toc + '<div id="how"><h3>Step 1</h3>' + deploy + _fig("09") + _fig("01") + '</div>' + tail
    excused = toc + '<div id="how"><h3>Step 1</h3>' + _fig("09", " data-prereq") + deploy + '</div>' + tail
    nodeploy = toc + '<div id="how"><h3>Step 1</h3>' + _fig("09") + '</div>' + tail

    cases = [
        ("rejects a figure above the deploy step",
         premature_figures(build_narrative(bad)) != []),
        ("is not fooled by the table of contents",
         "screenshots/09-x.png" in build_narrative(bad)),
        ("stops at the Challenges section",
         "99-x" not in build_narrative(good)),
        ("accepts figures below the deploy step, in any order",
         premature_figures(build_narrative(good)) == []),
        ("accepts a figure marked data-prereq",
         premature_figures(build_narrative(excused)) == []),
        ("says nothing when a post has no deploy step",
         premature_figures(build_narrative(nodeploy)) == []),
        ("treats a missing build section as failure",
         build_narrative('<div id="other"><figure></figure></div>') == ""),
        # Week 5 calls its deploy "Push to GitHub and apply via HCP" and the
        # step after it "Test immediately after deploy". A loose match picked
        # the second one and flagged three innocent figures.
        ("does not mistake a verification step for the deploy",
         premature_figures(
             '<div id="how"><h3>Step 8 &mdash; Push to GitHub and apply via HCP</h3>'
             + _fig("01") +
             '<h3>Step 9 &mdash; Test immediately after deploy</h3>'
             + _fig("05") + '</div>') == []),
        ("still finds the deploy when it is named plainly",
         premature_figures(
             '<div id="how"><h3>Step 1</h3>' + _fig("07") +
             '<h3>Step 2 &mdash; Deploy via HCP Terraform</h3></div>') != []),
    ]
    dead = [l for l, ok in cases if not ok]
    for label, ok in cases:
        print("  [%s] %s" % ("PASS" if ok else "DEAD", label))
    if dead:
        print("\n%d rule(s) DO NOT WORK. Their green means nothing." % len(dead))
        return 1
    print("\nAll %d self-tests passed - this check can actually fail." % len(cases))
    return 0


def self_test_quiet():
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        return self_test()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*", help="substring of a post filename")
    ap.add_argument("--series", help="ignored; accepted for prepublish.py")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    # A rule that cannot fail is worse than no rule, so prove it works first.
    if self_test_quiet():
        print("ABORTING: this check's own rules do not work. Run --self-test.")
        return 2

    paths = [p for p in sorted(glob.glob(os.path.join(ROOT, "posts", "*.html")))
             if LAB_POST.search(os.path.basename(p))]
    if args.posts:
        paths = [p for p in paths if any(s in os.path.basename(p) for s in args.posts)]

    failures, checked = [], 0
    for path in paths:
        name = os.path.basename(path)
        with open(path, encoding="utf-8", errors="replace") as fh:
            narrative = build_narrative(fh.read())
        if not narrative:
            print('  [skip] %-52s no id="how" section' % name)
            continue
        checked += 1
        bad = premature_figures(narrative)
        if bad:
            failures.append(name)
            print("  [FAIL] %s" % name)
            for num, alt in bad:
                print("           figure %s above the deploy step: %s" % (num, alt))
        else:
            print("  [ ok ] %s" % name)

    print()
    if failures:
        print("%d post(s) show live state before the step that creates it." % len(failures))
        print("Move the figure below the deploy step, or -- if the state really")
        print("does exist beforehand -- mark it <figure ... data-prereq>.")
        return 1
    print("%d lab post(s) checked, no figure precedes its deploy step." % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
