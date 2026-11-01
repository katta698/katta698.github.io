#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove named screenshots from a post, with the paragraph that introduces them.

    python scripts/drop_figures.py 8 01-hcp-plan 02-first-apply --write

The standard allows four to seven figures. Weeks 3, 4 and 8 carry fifteen,
sixteen and twelve, because the early posts screenshotted every step. The ones
to keep are the ones a reader cannot reconstruct from the text; the rest belong
in the lab guide, which is the exhaustive document by design.

A figure is usually preceded by a one-line paragraph that exists only to
introduce it ("Confirmed in the console:"). Those are removed too when they end
in a colon, because left behind they point at nothing.

It will not remove a figure it cannot find, and says so, rather than reporting
success for a name that never matched.
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

FIG = re.compile(r'<figure class="screenshot".*?</figure>\s*', re.S)


def drop(text, name):
    for m in FIG.finditer(text):
        if name not in m.group(0):
            continue
        start, end = m.start(), m.end()
        # Take a lead-in paragraph with it, if that is all it was.
        head = text[:start]
        pm = re.search(r"<p>[^<]{0,160}:</p>\s*$", head)
        if pm:
            start = pm.start()
        return text[:start] + text[end:], True
    return text, False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("week", type=int)
    ap.add_argument("names", nargs="+")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    p = paths.for_week(a.week)
    t = io.open(p, encoding="utf-8").read()
    before = len(FIG.findall(t))
    missing = []
    for n in a.names:
        t, ok = drop(t, n)
        if not ok:
            missing.append(n)
    after = len(FIG.findall(t))

    if missing:
        print("  no figure matched: %s" % ", ".join(missing))
    if a.write and not missing:
        io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("  week %-2d %s  %d figures -> %d"
          % (a.week, "dropped" if (a.write and not missing) else "would drop",
             before, after))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
