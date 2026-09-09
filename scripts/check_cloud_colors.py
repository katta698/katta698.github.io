#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One palette for AWS, Azure and Google, everywhere on the site.

    python scripts/check_cloud_colors.py
    python scripts/check_cloud_colors.py --list   # show every use

Why this exists
---------------
The three clouds are colour-coded in six different files -- the home page, the
blog stylesheet, the Intelligence hub, the What's New builder and the status
page -- and nothing connected them. They agreed by hand, until the status page
was given its own set (#E8A87C / #9DBEE0 / #A8C88A) and became the only page
where AWS was not sand and Google was not olive.

Worse had already happened and gone unnoticed: two of those files coloured
Google and Azure the SAME blue, 6 apart in RGB. A colour whose entire job is
telling the clouds apart was not doing it, in either theme, and no check could
see it because there was nothing that knew what the right colour was.

So the palette is written down once, here, and every file is checked against
it. A hex that is close but not equal is the failure mode this catches -- it
looks right in isolation and only shows up when a reader moves between pages.

Two layers, on purpose
----------------------
IDENTITY is the cloud's colour: edges, fills, borders. It never carries text,
because all three are mid-tones that fail AA on both the light and the dark
card.

TEXT is the same identity adjusted per theme, and it is what a chip or a label
uses. Keeping them separate is what lets the identity stay recognisable while
the readable version changes with the background.
"""
import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IDENTITY = {"aws": "#C4A484", "azure": "#5B7B9A", "gcp": "#8A9A5B"}

# Theme-adjusted, for text only.
TEXT_DARK = {"aws": "#D6B896", "azure": "#9DB6CE", "gcp": "#BCC98E"}
TEXT_LIGHT = {"aws": "#705539", "azure": "#3C5570", "gcp": "#515C32"}

APPROVED = {h.lower() for h in
            list(IDENTITY.values()) + list(TEXT_DARK.values())
            + list(TEXT_LIGHT.values())}

# Files that colour-code the clouds. Listed explicitly rather than globbed: a
# glob would sweep in generated pages, where a wrong colour is a symptom of a
# builder that is already covered here.
FILES = [
    "index.html",
    "blog/assets/blog.css",
    "intelligence/index.html",
    "intelligence/status/status.css",
    "scripts/build_news_page.py",
]

# A line is "about a cloud" if it names one AND sets a colour.
CLOUD = re.compile(r"\b(aws|azure|gcp)\b", re.I)
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
COLOURISH = re.compile(
    r"(color|background|border|--cloud-accent|--topic|--c-aws|--c-azure|--c-gcp"
    r"|--aws|--azure|--gcp)", re.I)


def scan():
    uses, bad = [], []
    for rel in FILES:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        for n, line in enumerate(io.open(p, encoding="utf-8", errors="replace"), 1):
            if not (CLOUD.search(line) and COLOURISH.search(line)):
                continue
            for h in HEX.findall(line):
                uses.append((rel, n, h, line.strip()[:88]))
                if h.lower() not in APPROVED:
                    bad.append((rel, n, h, line.strip()[:88]))
    return uses, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    uses, bad = scan()

    if args.list:
        for rel, n, h, line in uses:
            mark = " " if h.lower() in APPROVED else "!"
            print("  %s %-34s %4d  %s" % (mark, rel, n, h))
        print()

    # A check that examined nothing must not pass. If the file list rots or a
    # rename empties it, silence would read exactly like agreement.
    if not uses:
        print("  NO CLOUD COLOURS FOUND in %d file(s)." % len(FILES))
        print("  The files colour-code the clouds, so this means the scan is")
        print("  broken, not that the site is consistent.")
        return 1

    if bad:
        print("\n  OFF-PALETTE CLOUD COLOURS\n")
        for rel, n, h, line in bad:
            print("  %s:%d  %s" % (rel, n, h))
            print("      %s" % line)
        print("\n  %d use(s) outside the palette, of %d checked." % (len(bad), len(uses)))
        print("  The palette is:")
        for k in ("aws", "azure", "gcp"):
            print("    %-6s identity %s   text %s dark / %s light"
                  % (k, IDENTITY[k], TEXT_DARK[k], TEXT_LIGHT[k]))
        print("  A near-miss looks right on its own page and only shows up")
        print("  when a reader moves between pages.")
        return 1

    print("  %d cloud colour use(s) across %d file(s): all on palette."
          % (len(uses), len(FILES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
