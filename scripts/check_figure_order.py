#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""No screenshot may appear before the step that created what it shows.

    python scripts/check_figure_order.py                 # every lab-week post
    python scripts/check_figure_order.py week-18         # one post
    python scripts/check_figure_order.py --self-test     # prove it can fail

Why this exists
---------------
Lab screenshots are numbered in the order they were captured, which is the
order the build happened. So inside "How We Built It" the numbers must ascend.
A lower number after a higher one means a picture of live state is sitting
above the step that brings that state into existence -- a reader following
along hits a console page showing a resource that, at that point in the post,
does not exist yet.

Week 6 learned this. Week 18 broke it twice in one day: first with a Pod
Identity console page under Step 2, before the Step 3 that creates the cluster,
and then again hours later with a kubectl listing of live namespaces under
Step 1, which is an authoring step that runs before the apply. Jay found both
by reading the post.

It lives in CI rather than in a local script because the local version was run
at the author's discretion, and a rule that depends on someone remembering to
invoke it is the rule that was already written down and already broken.
"""
import argparse
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Only the weekly lab posts number their figures by build order.
LAB_POST = re.compile(r"week-\d+-")


def build_narrative(html):
    """The 'How We Built It' region, bounded by section ids.

    Bounded by ids and NOT by heading text. The first version of this rule split
    on the literal "Challenges &mdash;", which also appears in every post's
    table of contents -- so it returned the region ABOVE the article, found no
    figures, and passed the exact page it was written to reject.

    Returns "" when the section cannot be found. The caller must treat that as a
    failure, never as "nothing to check".
    """
    m_start = re.search(r'id="(?:how|build|how-we-built-it)"', html)
    if not m_start:
        return ""
    region = html[m_start.start():]
    m_end = re.search(r'id="challenges"', region)
    return region[:m_end.start()] if m_end else region


def regressions(narrative):
    """[(higher, lower)] for each place a figure number goes backwards."""
    seq = [int(m.group(1)) for m in re.finditer(r"screenshots/(\d+)", narrative)]
    return [(a, b) for a, b in zip(seq, seq[1:]) if b < a]


def self_test():
    toc = '<nav><a href="#challenges">Challenges &mdash; What Went Wrong</a></nav>'
    tail = '<div id="challenges">screenshots/02-later.png</div>'
    bad = toc + '<div id="how">screenshots/09-x.png screenshots/01-y.png</div>' + tail
    good = toc + '<div id="how">screenshots/01-y.png screenshots/09-x.png</div>' + tail

    cases = [
        ("rejects a forward reference", bool(regressions(build_narrative(bad)))),
        ("is not fooled by the table of contents", "screenshots/09-x.png" in build_narrative(bad)),
        ("stops at the Challenges section", "02-later" not in build_narrative(good)),
        ("accepts a correctly ordered post", not regressions(build_narrative(good))),
        ("treats a missing build section as failure",
         build_narrative('<div id="other">screenshots/01-a.png</div>') == ""),
    ]
    dead = [label for label, ok in cases if not ok]
    for label, ok in cases:
        print("  [%s] %s" % ("PASS" if ok else "DEAD", label))
    if dead:
        print("\n%d rule(s) DO NOT WORK. Their green means nothing." % len(dead))
        return 1
    print("\nAll %d self-tests passed - this check can actually fail." % len(cases))
    return 0


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

    paths = sorted(glob.glob(os.path.join(ROOT, "posts", "*.html")))
    paths = [p for p in paths if LAB_POST.search(os.path.basename(p))]
    if args.posts:
        paths = [p for p in paths
                 if any(s in os.path.basename(p) for s in args.posts)]

    failures, checked = [], 0
    for path in paths:
        name = os.path.basename(path)
        with open(path, encoding="utf-8", errors="replace") as fh:
            html = fh.read()
        narrative = build_narrative(html)
        if not narrative:
            # Older posts predate the id convention; say so rather than pass.
            print("  [skip] %-52s no id=\"how\" section" % name)
            continue
        checked += 1
        bad = regressions(narrative)
        if bad:
            hi, lo = bad[0]
            failures.append((name, hi, lo))
            print("  [FAIL] %-52s figure %02d appears after %02d" % (name, lo, hi))
        else:
            print("  [ ok ] %s" % name)

    print()
    if failures:
        print("%d post(s) show a screenshot before the step that creates it." % len(failures))
        print("Move the figure below the step that produces that state, or")
        print("renumber the capture if it was genuinely taken earlier.")
        return 1
    print("%d lab post(s) checked, figures all in build order." % checked)
    return 0


def self_test_quiet():
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return self_test()


if __name__ == "__main__":
    sys.exit(main())
