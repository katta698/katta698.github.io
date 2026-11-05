#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove the pre-standard decoration from a post's services section.

    python scripts/strip_legacy_services_cards.py 7 --write

Weeks 4, 6, 7 and 8 open their services section with the same three blocks:
"Required AWS Knowledge" and "Required Engineering Skills" as icon tag-grids,
then "Concepts to Understand Before Starting" as a grid of cards. Once the
three-column services table is in place those cards repeat it almost sentence
for sentence, and they are a large part of why these four posts run 1,000-1,500
words over the standard's budget.

This removes those blocks and nothing else. It does not touch prose paragraphs,
because a paragraph may carry a measured fact and a decorative grid cannot.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_lab_post_shape as shape      # noqa: E402
import aws_post_path as paths             # noqa: E402

# Headings whose whole block (heading + the grid that follows) goes.
DROP_HEADINGS = (
    "Required AWS Knowledge",
    "Required Engineering Skills",
    "Concepts to Understand Before Starting",
)


def _balanced_div(text, start):
    """End index of the <div ...> opening at `start`, including its </div>."""
    depth = 0
    i = start
    while i < len(text):
        if text.startswith("<div", i):
            depth += 1
            i += 4
        elif text.startswith("</div>", i):
            depth -= 1
            i += 6
            if depth == 0:
                return i
        else:
            i += 1
    return -1


def strip(section_html):
    out = section_html
    for heading in DROP_HEADINGS:
        while True:
            m = re.search(r"<h3>\s*%s\s*</h3>" % re.escape(heading), out)
            if not m:
                break
            after = out[m.end():]
            dm = re.search(r"<div[^>]*>", after)
            if not dm or dm.start() > 40:
                # Heading with no grid behind it -- drop the heading alone.
                out = out[:m.start()] + out[m.end():]
                continue
            abs_start = m.end() + dm.start()
            end = _balanced_div(out, abs_start)
            if end < 0:
                out = out[:m.start()] + out[m.end():]
                continue
            out = out[:m.start()] + out[end:]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("weeks", nargs="+", type=int)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    for wk in a.weeks:
        p = paths.for_week(wk)
        t = io.open(p, encoding="utf-8").read()
        sec = shape.section(t, "services")
        if sec is None:
            print("  week %-2d no services section" % wk)
            continue
        new = strip(sec)
        before = len(re.sub(r"<[^>]+>", " ", sec).split())
        after = len(re.sub(r"<[^>]+>", " ", new).split())
        if new == sec:
            print("  week %-2d nothing to strip" % wk)
            continue
        if a.write:
            io.open(p, "w", encoding="utf-8", newline="\n").write(
                t.replace(sec, new, 1))
        print("  week %-2d %s  %d -> %d words in the services section"
              % (wk, "stripped" if a.write else "would strip", before, after))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
