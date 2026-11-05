#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report, and optionally correct, a post's <div> balance.

    python scripts/fix_div_balance.py 6
    python scripts/fix_div_balance.py 6 --write

restructure_lab_post.py reassembles a post from its h2 boundaries. The early
posts wrap each section in a div that OPENS before its h2 and CLOSES after it,
so every opening tag sits at the end of the previous chunk; reordering the
chunks leaves those pairs crossed and the document a closer short or long.

Running normalise_section_divs.py --unwrap-only first removes the section divs
and most of the problem, but the post may still carry a container div whose
closer the reassembled tail does not account for.

The correction only ever touches TRAILING closers, or appends them at the end.
It will not insert a tag in the middle of the document, because at that point
the right answer is a judgement about which section a paragraph belongs to and
this script does not have one.
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

import aws_post_path as paths            # noqa: E402

TAG = re.compile(r"<div\b|</div\s*>")


def depth_of(text):
    d = 0
    for m in TAG.finditer(text):
        d += 1 if m.group(0).startswith("<div") else -1
    return d


def goes_negative_at(text):
    """Index where the running depth first drops below zero, or None."""
    d = 0
    for m in TAG.finditer(text):
        d += 1 if m.group(0).startswith("<div") else -1
        if d < 0:
            return m.start()
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("weeks", nargs="+", type=int)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    rc = 0
    for wk in a.weeks:
        p = paths.for_week(wk)
        t = io.open(p, encoding="utf-8").read()
        d = depth_of(t)
        if d == 0:
            print("  week %-2d balanced" % wk)
            continue

        bad = goes_negative_at(t)
        if bad is not None and d >= 0:
            print("  week %-2d REFUSED - closes too early at offset %d, so the "
                  "imbalance is structural, not trailing" % (wk, bad))
            rc = 1
            continue

        fixed = t
        if d > 0:
            fixed = t.rstrip() + "\n" + ("</div>\n" * d)
        else:
            for _ in range(-d):
                i = fixed.rstrip().rfind("</div>")
                if i < 0:
                    break
                fixed = fixed[:i] + fixed[i + 6:]
            fixed = fixed.rstrip() + "\n"

        if depth_of(fixed) != 0:
            print("  week %-2d REFUSED - correction did not balance it" % wk)
            rc = 1
            continue
        if a.write:
            io.open(p, "w", encoding="utf-8", newline="\n").write(fixed)
        print("  week %-2d %s  depth %+d -> 0 (%s %d trailing closer(s))"
              % (wk, "fixed" if a.write else "would fix", d,
                 "added" if d > 0 else "removed", abs(d)))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
