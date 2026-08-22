#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail a post whose inline SVG cannot survive being re-coloured or re-parented.

Why this check exists
---------------------
Week 1 of the Azure Weekly Lab shipped a diagram drawn with `currentColor` for
every stroke and label, plus opacity in the .5-.7 range to soften them. Inline in
the post it looked correct in both themes, and every existing check passed:
links resolved, structure validated, claims verified.

Then blog.js's magnifier re-parented the same SVG into the lightbox, which has
its own colour context. `currentColor` resolved to a pale value against a light
panel, the opacities took what was left, and the diagram was invisible. The only
elements that survived were the two hard-coded colours in the file.

No check caught it because every check was about *content*. This one is about
whether a diagram still renders when nothing around it is what it expected.

The rules
---------
An inline <svg> in a post must:

  1. Not use `currentColor` anywhere. It is a promise about the surrounding
     colour context, and a diagram that gets re-parented has no such promise.
  2. Paint its own background rect. Without one the diagram sits on whatever is
     behind it, which in a lightbox is not the page background it was drawn for.

Both rules are static, so this costs nothing and runs on every publish.

`--render` additionally drives a headless browser over the served pages in both
colour schemes and writes screenshots for eyeballing. That needs Playwright and
takes a few seconds per post, so it is opt-in rather than part of the gate --
the static rules are what actually block.

Usage:
  python scripts/check_theme_render.py                    # every served page
  python scripts/check_theme_render.py week-01-azure       # one post
  python scripts/check_theme_render.py --render --out /tmp/themes
"""

import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
POSTS = os.path.join(ROOT, "posts")

SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S)
# A background is any rect painted with a real colour that is not "none".
BG_RE = re.compile(r'<rect\b[^>]*\bfill="(?!none\b)[^"]+"', re.I)


def posts_to_check(selectors):
    names = sorted(f for f in os.listdir(POSTS) if f.endswith(".html"))
    if selectors:
        names = [n for n in names if any(sel in n for sel in selectors)]
    return [os.path.join(POSTS, n) for n in names]


def check_file(path):
    """Return a list of problem strings. Empty means the post is fine."""
    problems = []
    body = open(path, encoding="utf-8").read()

    for i, svg in enumerate(SVG_RE.findall(body), 1):
        # Tiny inline glyphs — icons, chevrons, the feedback star — are drawn to
        # follow the surrounding text on purpose, and are never lightboxed.
        # Judge by the viewBox, because that is what says "this is a diagram".
        vb = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"', svg)
        if vb and max(float(vb.group(1)), float(vb.group(2))) < 200:
            continue

        where = f"{os.path.basename(path)} svg#{i}"
        if "currentColor" in svg:
            n = svg.count("currentColor")
            problems.append(
                f"{where}: uses currentColor ({n}x). A lightboxed diagram has no "
                f"promise about the colour around it — use explicit colours."
            )
        if not BG_RE.search(svg):
            problems.append(
                f"{where}: paints no background. Add a rect covering the viewBox "
                f"so the diagram does not inherit whatever is behind it."
            )
    return problems


def render_both_schemes(paths, out_dir):
    """Screenshot each post's diagrams in light and dark, for eyeballing."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  --render needs playwright; skipping the visual pass")
        return

    os.makedirs(out_dir, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for path in paths:
            slug = os.path.basename(path)[:-5]
            served = os.path.join(ROOT, "blog", slug, "index.html")
            if not os.path.exists(served):
                continue
            for scheme in ("light", "dark"):
                page = browser.new_page(viewport={"width": 1280, "height": 900},
                                        color_scheme=scheme)
                page.goto("file:///" + served.replace(os.sep, "/"),
                          wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1200)
                el = page.query_selector(".arch-container")
                if el:
                    el.scroll_into_view_if_needed()
                    page.wait_for_timeout(400)
                    el.screenshot(path=os.path.join(out_dir, f"{slug}-{scheme}.png"))
                    print(f"  {slug} [{scheme}] -> {out_dir}")
                page.close()
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts", nargs="*", help="substrings of post filenames")
    ap.add_argument("--series", default=None, help="accepted for symmetry; unused")
    ap.add_argument("--render", action="store_true",
                    help="also screenshot diagrams in both colour schemes")
    ap.add_argument("--out", default=os.path.join(ROOT, ".theme-shots"))
    args = ap.parse_args()

    paths = posts_to_check(args.posts)
    if not paths:
        print("No posts matched.")
        return 0

    all_problems = []
    for path in paths:
        all_problems += check_file(path)

    if args.render:
        render_both_schemes(paths, args.out)

    if all_problems:
        print(f"THEME CHECK FAILED ({len(all_problems)} problem(s)):")
        for p in all_problems:
            print("  - " + p)
        print("")
        print("  A diagram that depends on the colour around it renders correctly")
        print("  inline and vanishes in the lightbox. Both rules are cheap to obey.")
        return 1

    n_svg = sum(len(SVG_RE.findall(open(p, encoding="utf-8").read())) for p in paths)
    print(f"  {len(paths)} post(s), {n_svg} inline svg(s): no currentColor, all painted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
