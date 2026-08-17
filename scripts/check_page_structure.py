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
    name = os.path.relpath(path, ROOT).replace("\\", "/")
    html = io.open(path, encoding="utf-8", errors="replace").read()
    out = []

    # 1. Post navigation must live in the post-nav, never the site header.
    for m in re.finditer(r'<a[^>]*class="post-nav-link (?:next|prev)"[^>]*>', html):
        if inside_header_nav(html, m.start()):
            kind = "next" if "next" in m.group(0) else "prev"
            out.append("%s link is inside the site header, not the post-nav" % kind)

    # 2. One next and one prev at most. Moving a link between navs can leave the
    #    page with two, which renders as two Next boxes pointing at the same
    #    post -- exactly what happened on azure-architecture-entra-identity-plane
    #    when the header copy was relocated into a post-nav that already had one.
    for kind in ("next", "prev"):
        n = len(re.findall(r'class="post-nav-link %s"' % kind, html))
        if n > 1:
            out.append("%d %s links; expected at most one" % (n, kind))

    # 3. Tag balance. An unclosed anchor swallows the rest of the page into a
    #    link; an unclosed nav does the same to the layout.
    for tag in ("a", "nav", "article", "main"):
        o = len(re.findall(r"<%s[\s>]" % tag, html))
        c = len(re.findall(r"</%s>" % tag, html))
        if o != c:
            out.append("<%s> unbalanced: %d open, %d close" % (tag, o, c))

    # 4. An unclosed HTML comment silently swallows everything after it.
    if html.count("<!--") != html.count("-->"):
        out.append("unbalanced HTML comment: %d open, %d close"
                   % (html.count("<!--"), html.count("-->")))

    # 5. Exactly one post-nav, and it should carry at least one link. An empty
    #    one renders as a stray bordered box at the foot of the post.
    navs = re.findall(r'<nav class="post-nav".*?</nav>', html, re.S)
    if len(navs) > 1:
        out.append("%d post-nav elements; expected at most one" % len(navs))
    for n in navs:
        if "post-nav-link" not in n:
            out.append("post-nav is present but empty")

    # 6. The page must actually be UTF-8. PowerShell has corrupted these before.
    try:
        io.open(path, "rb").read().decode("utf-8")
    except UnicodeDecodeError as exc:
        out.append("not valid UTF-8: %s" % exc)

    return name, out


def check_stylesheets():
    """A stray `*/` in CSS silently deletes the rule that follows it.

    This happened on 2026-08-17. An edit to blog.css left the previous comment's
    closing `*/` in place and added prose after it, so ~30 lines of English sat
    outside any comment as raw CSS. The parser recovers from that by discarding
    tokens up to the next `}` -- which was the Monday light-palette rule. So
    Monday, and only Monday, silently lost its palette and fell back to the
    :root default. It shipped, and the day it broke was the day it was pushed.

    Nothing caught it: the file still parsed, every other rule worked, contrast
    checks read the fallback values and called them fine, and the served CSS
    contained the rule -- the browser was dropping it, not the file.
    """
    out = []
    for path in sorted(glob.glob(os.path.join(ROOT, "blog", "assets", "*.css"))):
        name = os.path.relpath(path, ROOT).replace("\\", "/")
        css = io.open(path, encoding="utf-8", errors="replace").read()
        if css.count("/*") != css.count("*/"):
            out.append((name, "unbalanced CSS comment: %d /* and %d */"
                        % (css.count("/*"), css.count("*/"))))
        stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        if "*/" in stripped:
            i = stripped.index("*/")
            out.append((name, "stray '*/' outside a comment near %r -- the CSS "
                              "after it is discarded up to the next }"
                        % stripped[max(0, i - 45):i + 2].strip()[-60:]))
        if "/*" in stripped:
            out.append((name, "unterminated '/*' -- everything after it is a "
                              "comment"))
        o, c = stripped.count("{"), stripped.count("}")
        if o != c:
            out.append((name, "unbalanced braces: %d { and %d }" % (o, c)))
    return out


def collect():
    """Every page GitHub Pages actually serves.

    A first version globbed blog/*/index.html and called that "every page". It
    missed nine: the home page, resume, now, offline, the blog index itself and
    four pagination pages -- including the two most-visited pages on the site.
    A checker that quietly skips the front door is worse than none, because it
    reports clean.
    """
    seen, out = set(), []
    pats = ["index.html", "resume.html", "now.html", "offline.html",
            os.path.join("blog", "index.html"),
            os.path.join("blog", "*", "index.html"),
            os.path.join("blog", "page", "*", "index.html")]
    for pat in pats:
        for f in sorted(glob.glob(os.path.join(ROOT, pat))):
            rp = os.path.relpath(f, ROOT)
            if rp not in seen:
                seen.add(rp)
                out.append(f)
    return out


def main():
    quiet = "--quiet" in sys.argv
    pages = collect()
    bad = 0

    css_problems = check_stylesheets()
    for name, problem in css_problems:
        print("\n%s" % name)
        print("   %s" % problem)
    bad += len(css_problems)

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
