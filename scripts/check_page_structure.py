#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structural checks on every served page under blog/.

    python scripts/check_page_structure.py
    python scripts/check_page_structure.py --quiet     # only failures

Why this exists
---------------
Every other check here measures colour: contrast ratios between our own tokens.
None of them can see that an element rendered in the wrong place, and that is
how the Next link ended up inside the site header on 19 pages -- a link floating
over the top navigation, nowhere near the post it belonged to.

`fix_series_nav.py` inserted it before `html.index("</nav>")`, and these pages
have two nav elements: the site header at the top, the post-nav at the bottom.
The first one is the header. The script guarded on a post-nav EXISTING but not
on which one it wrote into, `validate_arch_post.py` checked the link's presence
and destination but not its position, and the contrast maths was measuring
something else entirely. Three checks, none of them looking at placement.

So this one asserts where things are, not what colour they are. Every rule below
corresponds to something that actually shipped broken.
"""
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAV_OPEN = re.compile(r"<nav[^>]*>")
NAV_CLOSE = re.compile(r"</nav>")


def inside_header_nav(html, pos):
    """True if `pos` falls inside the FIRST nav element (the site header)."""
    before = html[:pos]
    return len(NAV_OPEN.findall(before)) == 1 and len(NAV_CLOSE.findall(before)) == 0


def check(path):
    """Return a list of problems for one served page."""
    name = os.path.basename(os.path.dirname(path))
    html = io.open(path, encoding="utf-8", errors="replace").read()
    out = []

    # 1. Post navigation must live in the post-nav, never the site header.
    for m in re.finditer(r'<a[^>]*class="post-nav-link (?:next|prev)"[^>]*>', html):
        if inside_header_nav(html, m.start()):
            kind = "next" if "next" in m.group(0) else "prev"
            out.append("%s link is inside the site header, not the post-nav" % kind)

    # 2. Tag balance. An unclosed anchor swallows the rest of the page into a
    #    link; an unclosed nav does the same to the layout.
    for tag in ("a", "nav", "article", "main"):
        o = len(re.findall(r"<%s[\s>]" % tag, html))
        c = len(re.findall(r"</%s>" % tag, html))
        if o != c:
            out.append("<%s> unbalanced: %d open, %d close" % (tag, o, c))

    # 3. An unclosed HTML comment silently swallows everything after it.
    if html.count("<!--") != html.count("-->"):
        out.append("unbalanced HTML comment: %d open, %d close"
                   % (html.count("<!--"), html.count("-->")))

    # 4. Exactly one post-nav, and it should carry at least one link. An empty
    #    one renders as a stray bordered box at the foot of the post.
    navs = re.findall(r'<nav class="post-nav".*?</nav>', html, re.S)
    if len(navs) > 1:
        out.append("%d post-nav elements; expected at most one" % len(navs))
    for n in navs:
        if "post-nav-link" not in n:
            out.append("post-nav is present but empty")

    # 5. The page must actually be UTF-8. PowerShell has corrupted these before.
    try:
        io.open(path, "rb").read().decode("utf-8")
    except UnicodeDecodeError as exc:
        out.append("not valid UTF-8: %s" % exc)

    return name, out


def main():
    quiet = "--quiet" in sys.argv
    pages = sorted(glob.glob(os.path.join(ROOT, "blog", "*", "index.html")))
    bad = 0
    for p in pages:
        name, problems = check(p)
        if problems:
            bad += 1
            print("\n%s" % name)
            for x in problems:
                print("   %s" % x)
        elif not quiet:
            pass
    print("\nChecked %d page(s): %d with problems." % (len(pages), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
