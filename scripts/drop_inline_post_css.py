#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove the legacy inline <style> block from an early lab post.

    python scripts/drop_inline_post_css.py 1 2 3 4 5 6 7 8 --write

Weeks 1-8 each carry a 5-8 KB <style> block defining #jk-post and its classes.
Every post migrated to the Master Standard has none: sync_blog.py injects the
post stylesheet at build time, and the built page for week 25 carries 13 KB of
it covering every class these posts use, tag-grid and card included.

So the inline copy is dead weight in three ways. It duplicates the builder's
stylesheet, it can drift from it silently, and the shape check's word count
reads the CSS as prose -- about a thousand words per post, which is most of
the reason these eight look so far over the length budget.

Verified before writing this: the classes used by weeks 1-8 (toc, screenshot,
section, card, callout, code-block, code-header, tag-grid, grid-2,
post-header, post-meta, inline) are all present in the injected stylesheet.
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

# Classes the injected stylesheet is known to define. A post using something
# outside this set would lose its styling, so the removal refuses.
COVERED = {
    "toc", "screenshot", "section", "card", "callout", "code-block",
    "code-header", "code-lang", "code-dots", "code-dot", "tag-grid", "tag",
    "grid-2", "grid-3", "post-header", "post-eyebrow", "post-title",
    "post-subtitle", "post-meta", "inline", "icon", "icon-lg", "container",
    "amber", "red", "green", "blue", "table-scroll", "diagram", "muted",
}


def classes_used(html):
    out = set()
    for m in re.finditer(r'class="([^"]+)"', html):
        out.update(m.group(1).split())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("weeks", nargs="+", type=int)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    rc = 0
    for wk in a.weeks:
        p = paths.for_week(wk)
        t = io.open(p, encoding="utf-8").read()
        blocks = re.findall(r"<style[^>]*>.*?</style>", t, re.S)
        if not blocks:
            print("  week %-2d no inline style" % wk)
            continue
        stripped = re.sub(r"<style[^>]*>.*?</style>\s*", "", t, flags=re.S)
        unknown = sorted(classes_used(stripped) - COVERED)
        if unknown:
            print("  week %-2d REFUSED - classes not known to be covered: %s"
                  % (wk, ", ".join(unknown)))
            rc = 1
            continue
        if a.write:
            io.open(p, "w", encoding="utf-8", newline="\n").write(stripped)
        print("  week %-2d %s %d byte(s) of inline CSS"
              % (wk, "removed" if a.write else "would remove",
                 sum(len(b) for b in blocks)))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
