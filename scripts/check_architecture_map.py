#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every box on the architecture diagram still names something real.

    python scripts/check_architecture_map.py

Why this exists
---------------
/how-this-was-made/ prints, under the diagram: "Every box names a real file in
the repository -- a check refuses this page if one of them stops existing."

That sentence is either true or it is the most embarrassing kind of wrong, so
this is the check it refers to. A diagram is a promise about how something
fits together, and the failure mode is not that it breaks: it keeps rendering,
beautifully, describing a shape the code left behind months ago. Nobody
reports a diagram. They just quietly stop trusting it.

So this asserts two directions, because only one of them is easy:

  1. Every path the diagram claims exists.
  2. Every builder that writes a published page is ON the diagram.

The second is the one that catches drift. build_colophon.py itself was added
to this site after the diagram was drawn and is not in it -- caught by writing
this half of the check, not by looking at the picture.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# Builders that write a page a reader can open. A builder here and not on the
# diagram means the picture is missing a moving part.
#
# build_colophon.py is exempt for one honest reason: it is the builder OF the
# diagram, and drawing itself inside itself explains nothing. Named here
# rather than silently skipped, so the exemption is a decision somebody can
# disagree with rather than an omission.
EXEMPT_BUILDERS = {"build_colophon.py"}


def main():
    from colophon_architecture import CLAIMS, ARCHITECTURE

    problems = []

    # 1. Everything the picture names has to exist.
    print("  boxes on the diagram: %d" % len(CLAIMS))
    for label, rel in sorted(CLAIMS.items()):
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.exists(path):
            problems.append(
                "the diagram has a box labelled %r pointing at %s, which does "
                "not exist. The picture still renders and is now describing a "
                "site that is not this one" % (label, rel))
            print("     MISSING  %-26s %s" % (label, rel))

    # Every label in CLAIMS must actually appear in the drawing, or the check
    # is validating a list nobody is looking at.
    for label in CLAIMS:
        if label not in ARCHITECTURE:
            problems.append(
                "%r is in the claims list but does not appear in the drawing "
                "-- this check is guarding a box that is not there" % label)

    # 2. Every page-writing builder has to be in the picture.
    builders = [f for f in os.listdir(os.path.join(ROOT, "scripts"))
                if f.startswith("build_") and f.endswith(".py")]
    writes_page = []
    for f in sorted(builders):
        if f in EXEMPT_BUILDERS:
            continue
        try:
            src = io.open(os.path.join(ROOT, "scripts", f),
                          encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        # A builder that writes an index.html is one a reader meets.
        if re.search(r'["\']index\.html["\']', src):
            writes_page.append(f)

    for f in writes_page:
        if f not in ARCHITECTURE:
            problems.append(
                "%s writes a page a reader can open and is not on the "
                "diagram. The picture is missing a moving part, which is the "
                "way a diagram goes wrong: it keeps rendering" % f)
            print("     ABSENT   %s" % f)

    print("  builders that write a page: %d" % len(writes_page))

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for p in problems:
            print("  - %s" % p)
        print()
        print("  The page says every box names a real file. Either fix the")
        print("  diagram or stop printing that sentence under it.")
        return 1
    print("  Every box names something that exists, and every builder that "
          "writes\n  a page is on the picture.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
